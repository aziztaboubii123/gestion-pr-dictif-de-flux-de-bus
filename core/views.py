from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.db.utils import ProgrammingError
from datetime import date, timedelta
import json
import csv
import traceback

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/admin-dashboard/')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('/admin-dashboard/')
        else:
            return render(request, 'core/login.html', {'error': 'Identifiants invalides'})
    
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('/login/')

@login_required
def admin_dashboard(request):
    return render(request, 'core/admin_dashboard.html')

# ============= STATISTIQUES =============
@login_required
def api_stats(request):
    try:
        today = date.today()
        with connection.cursor() as cursor:
            # Correction : dateemission au lieu de dateemmision
            cursor.execute("SELECT COUNT(*) FROM alerte WHERE DATE(dateemission) = %s", [today])
            alertes_today = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM alerte WHERE dateemission >= CURRENT_DATE - INTERVAL '7 days'")
            open_alerts = cursor.fetchone()[0] or 0
            
            # Les autres compteurs (si les tables existent)
            try:
                cursor.execute("SELECT COUNT(*) FROM donnetrafic WHERE DATE(timestamp) = %s", [today])
                trips_today = cursor.fetchone()[0] or 0
            except:
                trips_today = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM bus WHERE statut = 'actif'")
                bus_actifs = cursor.fetchone()[0] or 0
            except:
                bus_actifs = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM bus")
                total_bus = cursor.fetchone()[0] or 0
            except:
                total_bus = 0
            try:
                cursor.execute("SELECT COALESCE(AVG(nombrepassager), 0) FROM donnetrafic WHERE DATE(timestamp) = %s AND nombrepassager > 0", [today])
                avg_passengers = cursor.fetchone()[0] or 0
            except:
                avg_passengers = 0
        
        return JsonResponse({
            'trips_today': trips_today,
            'infractions_today': alertes_today,
            'active_drivers': bus_actifs,
            'avg_score': avg_passengers,
            'total_drivers': total_bus,
            'open_alerts': open_alerts,
        })
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'trips_today': 0, 'infractions_today': 0, 'active_drivers': 0, 'avg_score': 0, 'total_drivers': 0, 'open_alerts': 0})

# ============= TRAJETS =============
@login_required
def api_trips(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT iddonnee, timestamp, vitesse, nombrepassagers, idbus
                FROM donneetrafic
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            rows = cursor.fetchall()

        data = []
        for row in rows:
            vitesse = row[2] or 0
            score = 100 if vitesse <= 50 else max(0, 100 - ((vitesse - 50) * 2))
            data.append({
                'id': f"T-{row[0]}",
                'name': f"Bus {row[3]}",  # idbus
                'av': f"B{row[3]}",
                'avc': 'av-blue',
                'date': row[1].strftime('%Y-%m-%d %H:%M') if row[1] else '',
                'ligne': f"Ligne {row[3]}",
                'passengers': row[3] or 0,   # attention: row[3] c'est nombrepassager ? Vérifiez l'ordre
                'vitesse': int(vitesse),
                'score': int(score),
            })
        return JsonResponse(data, safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse([], safe=False)

# ============= BUS =============
@login_required
def api_buses(request):
    try:
        with connection.cursor() as cursor:
            # Vérifier si la table bus existe
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bus')")
            if not cursor.fetchone()[0]:
                return JsonResponse([], safe=False)  # ← retour immédiat

            # Vérifier si donnetrafic existe
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'donnetrafic')")
            has_trafic = cursor.fetchone()[0]

            if has_trafic:
                query = """
                    SELECT b.idbus, b.immatriculation, b.modele, b.statut, b.kilometrage, 
                           COALESCE(l.numero, 'Non assigné') as ligne_numero, 
                           COUNT(d.iddonne) as total_donnees
                    FROM bus b
                    LEFT JOIN ligne l ON b.idligne = l.idligne
                    LEFT JOIN donnetrafic d ON b.idbus = d.idbus
                """
            else:
                query = """
                    SELECT b.idbus, b.immatriculation, b.modele, b.statut, b.kilometrage, 
                           COALESCE(l.numero, 'Non assigné') as ligne_numero,
                           0 as total_donnees
                    FROM bus b
                    LEFT JOIN ligne l ON b.idligne = l.idligne
                """

            query += " WHERE 1=1"
            params = []

            status = request.GET.get('status')
            if status and status != 'all':
                query += " AND b.statut = %s"
                params.append(status)

            search = request.GET.get('search', '')
            if search:
                query += " AND (b.immatriculation ILIKE %s OR b.modele ILIKE %s)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])

            query += " GROUP BY b.idbus, l.numero ORDER BY b.immatriculation"

            cursor.execute(query, params)
            rows = cursor.fetchall()

        data = []
        for row in rows:
            status_map = {
                'actif': ('b-green', 'Actif'),
                'maintenance': ('b-amber', 'Maintenance'),
                'hors_ligne': ('b-red', 'Hors ligne')
            }
            status_class, status_text = status_map.get(row[3], ('b-gray', row[3] or 'Inconnu'))

            data.append({
                'name': f"Bus {row[1]}",
                'av': row[1][:2].upper() if row[1] else "BU",
                'avc': 'av-blue',
                'id': f"B-{row[0]}",
                'ligne': row[5] if row[5] else 'Non assigné',
                'status': row[3] or 'inactif',
                'trips': int(row[6] or 0),
                'score': 75,
                'infractions': 0,
                'modele': row[2],
                'kilometrage': float(row[4] or 0),
                'status_class': status_class,
                'status_text': status_text,
            })

        return JsonResponse(data, safe=False)   # ← retour normal

    except Exception as e:
        traceback.print_exc()
        return JsonResponse([], safe=False)     # ← retour en cas d'erreur

# ============= ALERTES (CORRIGÉE POUR VOTRE TABLE) =============
@login_required
def api_alerts(request):
    try:
        with connection.cursor() as cursor:
            # Utiliser le bon nom de colonne : dateemission
            cursor.execute("""
                SELECT idalerte, message, niveau, dateemission
                FROM alerte
                ORDER BY dateemission DESC
            """)
            rows = cursor.fetchall()
        
        data = []
        for row in rows:
            message = row[1] or ''
            if 'phone' in message.lower():
                icon = "📱"
                priority = "high"
            elif 'closed_eye' in message.lower():
                icon = "😴"
                priority = "high"
            else:
                icon = "🔔"
                priority = "medium"
            
            data.append({
                'id': f"A-{row[0]}",
                'type': row[2] or 'warning',
                'icon': icon,
                'title': message[:50],
                'desc': message,
                'time': row[3].strftime('%H:%M') if row[3] else '',
                'driver': 'Système',
                'status': 'open',
                'priority': priority,
            })
        return JsonResponse(data, safe=False)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse([], safe=False)

# ============= LIGNES =============
@login_required
def api_lines(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'ligne'
                )
            """)
            if not cursor.fetchone()[0]:
                return JsonResponse([], safe=False)
        
        query = """
            SELECT l.idligne, l.numero, l.frequence, COUNT(DISTINCT a.idarret) as nb_arrets
            FROM ligne l
            LEFT JOIN arret a ON l.idligne = a.idligne
            GROUP BY l.idligne
            ORDER BY l.numero
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
        
        data = []
        colors = ['#4f8ef7', '#22c55e', '#ef4444', '#14b8a6', '#a855f7', '#f59e0b', '#6366f1']
        for i, row in enumerate(rows):
            data.append({
                'name': f"Ligne {row[1]}",
                'color': colors[i % len(colors)],
                'km': 0,
                'stops': [],
                'trajets': row[3] or 0,
                'passagers': 0,
                'score': 75,
                'status': 'ok',
                'frequence': row[2] or 0,
            })
        
        return JsonResponse(data, safe=False)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse([], safe=False)

# ============= RÉSOUDRE UNE ALERTE =============
@login_required
@require_http_methods(['POST'])
def resolve_alert(request):
    try:
        data = json.loads(request.body)
        alert_id = data.get('id')
        if alert_id:
            alert_id_clean = alert_id.replace('A-', '')
            with connection.cursor() as cursor:
                # Option 1 : supprimer l'alerte (si vous voulez la résoudre en la supprimant)
                cursor.execute("DELETE FROM alerte WHERE idalerte = %s", [alert_id_clean])
                # Option 2 : marquer comme résolue (nécessite une colonne 'statut')
                # cursor.execute("UPDATE alerte SET statut = 'resolved' WHERE idalerte = %s", [alert_id_clean])
        return JsonResponse({'success': True})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

# ============= AJOUTER UN BUS =============
@login_required
@require_http_methods(['POST'])
def save_bus(request):
    try:
        data = json.loads(request.body)
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO bus (immatriculation, modele, statut, kilometrage, idligne)
                VALUES (%s, %s, %s, %s, %s)
            """, [
                data.get('immatriculation', ''),
                data.get('modele', ''),
                data.get('statut', 'actif'),
                float(data.get('kilometrage', 0)),
                data.get('idligne') if data.get('idligne') else None
            ])
        return JsonResponse({'success': True})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

# ============= EXPORT CSV =============
@login_required
def export_data(request):
    try:
        # Vérifier si la table donnetrafic existe
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'donnetrafic'
                )
            """)
            if not cursor.fetchone()[0]:
                # Si la table n'existe pas, on exporte les alertes à la place
                return export_alerts_csv(request)
        
        query = """
            SELECT d.iddonne, d.timestamp, d.vitesse, d.nombrepassager, 
                   d.tauxoccupation, COALESCE(b.immatriculation, 'Inconnu') as immatriculation,
                   COALESCE(l.numero, '?') as ligne_numero
            FROM donnetrafic d
            LEFT JOIN bus b ON d.idbus = b.idbus
            LEFT JOIN ligne l ON b.idligne = l.idligne
            ORDER BY d.timestamp DESC LIMIT 1000
        """
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transport_data_export.csv"'
        response.write('\ufeff'.encode('utf-8'))
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Date/Heure', 'Vitesse (km/h)', 'Passagers', 'Taux Occupation (%)', 'Bus', 'Ligne'])
        
        for row in rows:
            writer.writerow([
                row[0], row[1].strftime('%Y-%m-%d %H:%M:%S') if row[1] else '',
                row[2] or 0, row[3] or 0, row[4] or 0, row[5] or '', row[6] or '',
            ])
        return response
    except Exception as e:
        traceback.print_exc()
        return HttpResponse("Erreur lors de l'export", status=500)

def export_alerts_csv(request):
    """Export de la table alerte si donnetrafic n'existe pas"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT idalerte, message, niveau, dateemmision FROM alerte ORDER BY dateemmision DESC")
        rows = cursor.fetchall()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="alertes_export.csv"'
    response.write('\ufeff'.encode('utf-8'))
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Message', 'Niveau', 'Date d\'émission'])
    
    for row in rows:
        writer.writerow([
            row[0], row[1], row[2], row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else ''
        ])
    return response