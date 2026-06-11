/* ================= DATA FROM DJANGO ================= */
const arrets = JSON.parse('{{ arrets_geojson|escapejs }}');
const lignes = JSON.parse('{{ lignes_geojson|escapejs }}');

// Variable globale pour suivre la ligne sélectionnée
let selectedLine = null;
let currentSearchTerm = "";
let currentMapLayer = 'osm'; // 'osm' ou 'satellite'

// Base de connaissances du chatbot
const chatbotKnowledge = {
  horaires: {
    semaine: "5h30 - 23h00",
    weekend: "6h00 - 22h30",
    frequence: "10-15 minutes aux heures de pointe, 20-30 minutes aux heures creuses"
  },
  tarifs: {
    ticket: "1.50€",
    carte: "15€ pour 10 voyages",
    mensuel: "45€",
    abonnement: "Abonnements étudiants : 30€, seniors : 35€"
  },
  contact: {
    telephone: "+216 71 123 456",
    email: "support@wasilni.tn",
    adresse: "15 Avenue de la Liberté, Tunis"
  },
  infos: {
    nombre_lignes: lignes.features.length,
    nombre_stations: arrets.features.length,
    ville: "Tunis et sa région"
  }
};

/* ================= COUCHES DE CARTE ================= */
const OSM = new ol.layer.Tile({
  source: new ol.source.OSM(),
  title: 'OpenStreetMap',
  visible: true
});

const ESRI_Imagery = new ol.layer.Tile({
  source: new ol.source.XYZ({
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
  }),
  title: 'ESRI Imagery',
  visible: false
});

const stationLayer = new ol.layer.Vector({
  source: new ol.source.Vector(),
  title: 'Bus stations'
});

const lineLayer = new ol.layer.Vector({
  source: new ol.source.Vector(),
  title: 'Bus lines'
});

const map = new ol.Map({
  target: 'map',
  layers: [ESRI_Imagery, OSM, lineLayer, stationLayer],
  view: new ol.View({
    center: ol.proj.fromLonLat([10.18, 36.8]),
    zoom: 12
  })
});

/* ================= FONCTION DE BASCULEMENT DE CARTE ================= */
function toggleMapLayer() {
  if (currentMapLayer === 'osm') {
    OSM.setVisible(false);
    ESRI_Imagery.setVisible(true);
    currentMapLayer = 'satellite';
    document.getElementById('mapToggleText').textContent = 'Carte';
    document.getElementById('mapToggleIcon').className = 'fas fa-globe';
    addBotMessage("🌍 Mode satellite activé");
  } else {
    OSM.setVisible(true);
    ESRI_Imagery.setVisible(false);
    currentMapLayer = 'osm';
    document.getElementById('mapToggleText').textContent = 'Satellite';
    document.getElementById('mapToggleIcon').className = 'fas fa-satellite';
    addBotMessage("🗺️ Mode carte standard activé");
  }
}

/* ================= STATIONS ================= */
arrets.features.forEach(f => {
  const lonlat = f.geometry.coordinates;

  const feature = new ol.Feature({
    geometry: new ol.geom.Point(ol.proj.fromLonLat(lonlat)),
    info: f.properties
  });

  const style = new ol.style.Style({
    image: new ol.style.Icon({
      src: "https://cdn-icons-png.flaticon.com/512/61/61231.png",
      scale: 0.05
    })
  });

  feature.setStyle(style);
  feature.set("originalStyle", style);
  feature.set("originalColor", "#00c896");

  stationLayer.getSource().addFeature(feature);
});

/* ================= LIGNES ================= */
lignes.features.forEach(f => {
  const coords = f.geometry.coordinates.map(c => ol.proj.fromLonLat(c));

  const feature = new ol.Feature({
    geometry: new ol.geom.LineString(coords),
    info: f.properties
  });

  const num = parseInt(f.properties.numero) || 0;
  const hue = (num * 50) % 360;
  const color = `hsl(${hue}, 80%, 50%)`;
  
  const style = new ol.style.Style({
    stroke: new ol.style.Stroke({color: color, width: 3})
  });
  
  const highlightStyle = new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: '#FFD700',
      width: 6,
      lineDash: [10, 5]
    })
  });
  
  const selectedStyle = new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: '#FF4500',
      width: 8,
      lineDash: []
    })
  });

  feature.setStyle(style);
  feature.set("originalStyle", style);
  feature.set("highlightStyle", highlightStyle);
  feature.set("selectedStyle", selectedStyle);
  feature.set("originalColor", color);
  feature.set("numero", f.properties.numero);
  feature.set("nom", f.properties.nom || `Ligne ${f.properties.numero}`);

  lineLayer.getSource().addFeature(feature);

  const option = document.createElement("option");
  option.value = f.properties.numero;
  option.text = "Ligne " + f.properties.numero;
  document.getElementById("lineSelect").appendChild(option);
});

/* ================= POPUP ================= */
const popup = document.getElementById('popup');
const overlay = new ol.Overlay({ element: popup, offset: [0, -15] });
map.addOverlay(overlay);

map.on('click', evt => {
  const feature = map.forEachFeatureAtPixel(evt.pixel, f => f);
  if (feature) {
    const info = feature.get('info');
    popup.innerHTML = `<strong>${info.nom || "Ligne " + info.numero}</strong>`;
    overlay.setPosition(evt.coordinate);
  } else overlay.setPosition(undefined);
});

/* ================= GESTIONNAIRE POUR LA LISTE DÉROULANTE ================= */
function handleLineSelect(lineValue) {
  if (lineValue === "all") {
    clearLineSelection();
    document.getElementById("searchInput").value = "";
    currentSearchTerm = "";
    searchMap();
    addBotMessage("Affichage de toutes les lignes");
  } else {
    selectLine(lineValue);
    document.getElementById("searchInput").value = `Ligne ${lineValue}`;
    currentSearchTerm = `ligne ${lineValue}`;
    addBotMessage(`🔍 Ligne ${lineValue} sélectionnée`);
  }
}

/* ================= SÉLECTIONNER UNE LIGNE ================= */
function selectLine(lineNumero) {
  selectedLine = lineNumero;
  const highlightOnly = document.getElementById("highlightOnly").checked;
  
  document.getElementById("selectedLineInfo").style.display = "block";
  document.getElementById("selectedLineBadge").textContent = `Ligne ${lineNumero} sélectionnée`;
  
  lineLayer.getSource().getFeatures().forEach(f => {
    const fNumero = f.get('numero')?.toString() || (f.get('info')?.numero?.toString() || '');
    
    if (fNumero === lineNumero.toString()) {
      f.setStyle(f.get("selectedStyle"));
      
      const geometry = f.getGeometry();
      if (geometry) {
        const extent = geometry.getExtent();
        map.getView().fit(extent, {
          padding: [100, 100, 100, 100],
          duration: 1000,
          maxZoom: 15
        });
      }
    } else {
      f.setStyle(highlightOnly ? null : f.get("originalStyle"));
    }
  });
  
  updateSelectionStats();
}

/* ================= RECHERCHE AVEC SURBRILLANCE ================= */
function searchMap() {
  const value = document.getElementById("searchInput").value.toLowerCase().trim();
  currentSearchTerm = value;
  const highlightOnly = document.getElementById("highlightOnly").checked;
  
  if (selectedLine !== null && value !== `ligne ${selectedLine}` && value !== selectedLine.toString()) {
    selectedLine = null;
    document.getElementById("selectedLineInfo").style.display = "none";
    document.getElementById("lineSelect").value = "all";
  }
  
  let visibleLines = 0;
  let visibleStations = 0;
  let highlightedLines = [];
  
  if (value === "") {
    lineLayer.getSource().getFeatures().forEach(f => {
      f.setStyle(f.get("originalStyle"));
      visibleLines++;
    });
    
    stationLayer.getSource().getFeatures().forEach(f => {
      f.setStyle(f.get("originalStyle"));
      visibleStations++;
    });
    
    selectedLine = null;
    document.getElementById("selectedLineInfo").style.display = "none";
    document.getElementById("lineSelect").value = "all";
  } else {
    lineLayer.getSource().getFeatures().forEach(f => {
      const numero = f.get('numero')?.toString().toLowerCase() || '';
      const nom = f.get('nom')?.toLowerCase() || '';
      const info = f.get('info');
      const infoNumero = info?.numero?.toString().toLowerCase() || '';
      const infoNom = info?.nom?.toLowerCase() || '';
      
      const matches = numero.includes(value) || 
                      nom.includes(value) || 
                      infoNumero.includes(value) || 
                      infoNom.includes(value);
      
      if (matches) {
        if (selectedLine && (numero === selectedLine.toString() || infoNumero === selectedLine.toString())) {
          f.setStyle(f.get("selectedStyle"));
        } else {
          f.setStyle(f.get("highlightStyle"));
        }
        visibleLines++;
        highlightedLines.push(f.get('numero') || f.get('info').numero);
      } else {
        f.setStyle(highlightOnly ? null : f.get("originalStyle"));
      }
    });

    stationLayer.getSource().getFeatures().forEach(f => {
      const info = f.get('info');
      const nom = info?.nom?.toLowerCase() || '';
      
      if (nom.includes(value)) {
        f.setStyle(f.get("originalStyle"));
        visibleStations++;
      } else {
        f.setStyle(highlightOnly ? null : f.get("originalStyle"));
      }
    });
  }
  
  updateSearchStats(value, visibleLines, visibleStations, highlightedLines);
}

/* ================= GESTIONNAIRE POUR L'OPTION "MASQUER LES AUTRES" ================= */
function handleHighlightOnlyChange() {
  if (selectedLine) {
    selectLine(selectedLine);
  } else {
    searchMap();
  }
}

/* ================= STATISTIQUES DE RECHERCHE ================= */
function updateSearchStats(searchTerm, visibleLines, visibleStations, highlightedLines = []) {
  const statsDiv = document.getElementById('searchStats');
  
  if (searchTerm === "") {
    statsDiv.innerHTML = `${visibleLines} lignes, ${visibleStations} stations`;
  } else {
    let statsHtml = `🔍 "${searchTerm}" : `;
    
    if (highlightedLines.length > 0) {
      statsHtml += `<span class="highlight-color">${highlightedLines.length} ligne(s) trouvée(s)</span>`;
      if (visibleStations > 0) {
        statsHtml += `, ${visibleStations} station(s)`;
      }
      
      const uniqueLines = [...new Set(highlightedLines)];
      statsHtml += `<br><small>Lignes: ${uniqueLines.join(', ')}</small>`;
      
      if (selectedLine) {
        statsHtml += `<br><span class="selected-line-badge">Sélectionnée: Ligne ${selectedLine}</span>`;
      }
    } else if (visibleStations > 0) {
      statsHtml += `${visibleStations} station(s) trouvée(s)`;
    } else {
      statsHtml += `<span style="color:#ff6b6b">Aucun résultat</span>`;
    }
    
    statsDiv.innerHTML = statsHtml;
  }
}

/* ================= STATISTIQUES DE SÉLECTION ================= */
function updateSelectionStats() {
  const statsDiv = document.getElementById('searchStats');
  if (selectedLine) {
    statsDiv.innerHTML = `<span class="highlight-color">Ligne ${selectedLine} sélectionnée</span>`;
  }
}

/* ================= FILTER BUS ================= */
function filterBus(type) {
  stationLayer.getSource().getFeatures().forEach(f => {
    if (type === "all") {
      f.setStyle(f.get("originalStyle"));
    }
    if (type === "visible") {
      const extent = map.getView().calculateExtent(map.getSize());
      const coord = f.getGeometry().getCoordinates();
      if (ol.extent.containsCoordinate(extent, coord)) {
        f.setStyle(f.get("originalStyle"));
      } else {
        f.setStyle(null);
      }
    }
  });
}

/* ================= RÉINITIALISER LA SÉLECTION ================= */
function clearLineSelection() {
  selectedLine = null;
  document.getElementById("selectedLineInfo").style.display = "none";
  document.getElementById("lineSelect").value = "all";
  document.getElementById("searchInput").value = "";
  currentSearchTerm = "";
  searchMap();
}

/* ================= RÉINITIALISER LA RECHERCHE ================= */
function clearSearch() {
  clearLineSelection();
}

/* ================= CENTRER SUR LA LIGNE TROUVÉE ================= */
function zoomToLine(lineNumero) {
  const features = lineLayer.getSource().getFeatures();
  for (let f of features) {
    const fNumero = f.get('numero') || (f.get('info') && f.get('info').numero);
    if (fNumero && fNumero.toString() === lineNumero.toString()) {
      const geometry = f.getGeometry();
      if (geometry) {
        const extent = geometry.getExtent();
        map.getView().fit(extent, {
          padding: [100, 100, 100, 100],
          duration: 1000,
          maxZoom: 15
        });
      }
      break;
    }
  }
}

/* ================= PANELS ================= */
function openPanel(type) {
  const panel = document.getElementById("panel");
  const content = document.getElementById("panelContent");

  if (type === "dashboard")
    content.innerHTML = "<h4>Vue générale</h4>Suivi temps réel du réseau.";

  if (type === "bus")
    content.innerHTML = "<h4>Bus actifs</h4>A compléter";

  if (type === "stations")
    content.innerHTML = "<h4>Stations</h4>" + arrets.features.map(a => a.properties.nom).join("<br>");

  if (type === "alerts")
    content.innerHTML = "<h4>Alertes</h4>Aucun incident";

  panel.style.display = "block";
}

function closePanel() {
  document.getElementById("panel").style.display = "none"
}

/* ================= FONCTIONS DU CHATBOT INTELLIGENT ================= */
let chatbotOpen = false;
let unreadMessages = 0;

function toggleChatbot() {
  const container = document.getElementById('chatbotContainer');
  const toggle = document.getElementById('chatbotToggle');
  
  if (chatbotOpen) {
    container.style.display = 'none';
    toggle.style.backgroundColor = '#00c896';
    toggle.style.color = '#020617';
    unreadMessages = 0;
    document.getElementById('chatbotNotification').style.display = 'none';
  } else {
    container.style.display = 'flex';
    toggle.style.backgroundColor = '#020617';
    toggle.style.color = '#00c896';
  }
  
  chatbotOpen = !chatbotOpen;
}

function addUserMessage(text) {
  const messages = document.getElementById('chatbotMessages');
  const timestamp = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  
  messages.innerHTML += `
    <div class="message user-message">
      ${text}
      <div class="timestamp">${timestamp}</div>
    </div>
  `;
  
  messages.scrollTop = messages.scrollHeight;
}

function addBotMessage(text) {
  const messages = document.getElementById('chatbotMessages');
  const timestamp = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  
  // Supprimer l'indicateur de typing s'il existe
  const typingIndicator = document.querySelector('.typing-indicator');
  if (typingIndicator) {
    typingIndicator.remove();
  }
  
  messages.innerHTML += `
    <div class="message bot-message">
      ${text}
      <div class="timestamp">${timestamp}</div>
    </div>
  `;
  
  messages.scrollTop = messages.scrollHeight;
  
  // Notification si le chatbot est fermé
  if (!chatbotOpen) {
    unreadMessages++;
    document.getElementById('chatbotNotification').style.display = 'flex';
    document.getElementById('chatbotNotification').textContent = unreadMessages;
  }
}

function showTypingIndicator() {
  const messages = document.getElementById('chatbotMessages');
  
  messages.innerHTML += `
    <div class="typing-indicator">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  
  messages.scrollTop = messages.scrollHeight;
}

function getLineInfo(lineNumber) {
  const line = lignes.features.find(f => f.properties.numero == lineNumber);
  if (line) {
    return {
      nom: line.properties.nom || `Ligne ${lineNumber}`,
      stations: line.properties.stations || "Information non disponible",
      couleur: line.properties.couleur || "Non spécifiée"
    };
  }
  return null;
}

function getStationInfo(stationName) {
  const station = arrets.features.find(f => 
    f.properties.nom.toLowerCase().includes(stationName.toLowerCase())
  );
  return station ? station.properties : null;
}

function processBotResponse(userMessage) {
  const message = userMessage.toLowerCase().trim();
  
  showTypingIndicator();
  
  setTimeout(() => {
    // Salutations
    if (message.match(/bonjour|salut|hello|coucou|hey|bjr/i)) {
      const heures = new Date().getHours();
      let moment = "bonne journée";
      if (heures < 12) moment = "bonne matinée";
      else if (heures < 18) moment = "bon après-midi";
      else moment = "bonne soirée";
      
      addBotMessage(`👋 Bonjour ! Passez une ${moment}. Comment puis-je vous aider avec le réseau Wasilni ?`);
    }

    // Questions sur les lignes
    else if (message.match(/lignes? (?:\d+)/i)) {
      const lineNum = message.match(/\d+/)[0];
      const lineInfo = getLineInfo(lineNum);
      
      if (lineInfo) {
        addBotMessage(`🚍 <strong>Ligne ${lineNum}</strong><br><br>
        📍 Nom: ${lineInfo.nom}<br>
        🎨 Couleur: ${lineInfo.couleur}<br>
        🚏 Stations: ${lineInfo.stations}<br><br>
        Je peux afficher cette ligne sur la carte si vous le souhaitez.`);
        
        // Optionnel: afficher la ligne sur la carte
        document.getElementById('searchInput').value = `Ligne ${lineNum}`;
        searchMap();
      } else {
        addBotMessage(`❌ Désolé, je n'ai pas trouvé d'information sur la ligne ${lineNum}.`);
      }
    }

    // Liste de toutes les lignes
    else if (message.match(/toutes? (?:les )?lignes|liste des lignes|quelles lignes/i)) {
      const lignesList = lignes.features.map(f => f.properties.numero).sort((a,b) => a - b);
      addBotMessage(`📋 <strong>Lignes disponibles (${lignesList.length}) :</strong><br><br>
      ${lignesList.join(' • ')}<br><br>
      Tapez "Ligne X" pour plus d'informations sur une ligne spécifique.`);
    }

    // Horaires
    else if (message.match(/horaire|heure|quand|horaires|temps d'attente|fréquence/i)) {
      addBotMessage(`🕐 <strong>Horaires de service :</strong><br><br>
      • Semaine: ${chatbotKnowledge.horaires.semaine}<br>
      • Weekend: ${chatbotKnowledge.horaires.weekend}<br>
      • Fréquence: ${chatbotKnowledge.horaires.frequence}<br><br>
      ℹ️ Les horaires peuvent varier selon les lignes et les jours fériés.`);
    }

    // Tarifs et prix
    else if (message.match(/tarif|prix|combien coûte|payer|ticket|billet|abonnement|carte/i)) {
      addBotMessage(`💰 <strong>Tarifs en vigueur :</strong><br><br>
      • Ticket unitaire: ${chatbotKnowledge.tarifs.ticket}<br>
      • Carte 10 voyages: ${chatbotKnowledge.tarifs.carte}<br>
      • Abonnement mensuel: ${chatbotKnowledge.tarifs.mensuel}<br>
      • Tarifs réduits: ${chatbotKnowledge.tarifs.abonnement}<br><br>
      Paiement accepté en espèces, carte bancaire et carte de transport.`);
    }

    // Stations/Arrêts
    else if (message.match(/station|arrêt|où se trouve|localisation/i)) {
      if (message.match(/station (.+)/i)) {
        const stationName = message.match(/station (.+)/i)[1];
        const station = getStationInfo(stationName);
        
        if (station) {
          addBotMessage(`📍 <strong>Station ${station.nom}</strong><br><br>
          • Lignes desservies: ${station.lignes || "Information non disponible"}<br>
          • Équipements: ${station.equipements || "Standard"}<br>
          • Accessibilité: ${station.accessibilite || "Oui"}<br><br>
          La station est affichée sur la carte.`);
        } else {
          addBotMessage(`❌ Station "${stationName}" non trouvée.`);
        }
      } else {
        const stationsList = arrets.features.map(f => f.properties.nom).slice(0, 10);
        addBotMessage(`📍 <strong>Principales stations (${arrets.features.length} total) :</strong><br><br>
        ${stationsList.join('<br>')}${arrets.features.length > 10 ? '<br>...' : ''}<br><br>
        Tapez "Station [nom]" pour plus de détails.`);
      }
    }

    // Itinéraire
    else if (message.match(/itinéraire|comment aller|trajet|chemin|route|aller de|vers/i)) {
      addBotMessage(`🗺️ <strong>Planification d'itinéraire</strong><br><br>
      Pour calculer un itinéraire, j'ai besoin de :<br>
      1️⃣ Point de départ<br>
      2️⃣ Point d'arrivée<br><br>
      Exemple: "Comment aller de La Marsa à Tunis Centre ?"`);
    }

    // Contact et support
    else if (message.match(/contact|téléphone|email|adresse|joindre|support|aide humaine/i)) {
      addBotMessage(`📞 <strong>Nous contacter :</strong><br><br>
      • Téléphone: ${chatbotKnowledge.contact.telephone}<br>
      • Email: ${chatbotKnowledge.contact.email}<br>
      • Adresse: ${chatbotKnowledge.contact.adresse}<br><br>
      Notre service client est disponible du lundi au vendredi de 8h à 18h.`);
    }

    // Problèmes techniques
    else if (message.match(/problème|panne|incident|retard|bug|ne marche pas|erreur/i)) {
      addBotMessage(`🔧 <strong>Support technique</strong><br><br>
      Je détecte un problème technique. Voici ce que vous pouvez faire :<br><br>
      1️⃣ Vérifier votre connexion internet<br>
      2️⃣ Rafraîchir la page (F5)<br>
      3️⃣ Vider le cache du navigateur<br><br>
      Si le problème persiste, contactez notre support au ${chatbotKnowledge.contact.telephone}`);
    }

    // Informations générales sur le réseau
    else if (message.match(/réseau|information générale|statistiques|à propos|info réseau|combien de/i)) {
      addBotMessage(`📊 <strong>Informations sur le réseau Wasilni</strong><br><br>
      • Nombre de lignes: ${chatbotKnowledge.infos.nombre_lignes}<br>
      • Nombre de stations: ${chatbotKnowledge.infos.nombre_stations}<br>
      • Zone desservie: ${chatbotKnowledge.infos.ville}<br>
      • Première ligne: 6h00 - Dernière ligne: 23h00<br><br>
      Wasilni dessert plus de 500 000 voyageurs chaque jour.`);
    }

    // Mode carte
    else if (message.match(/satellite|vue satellite|image satellite/i)) {
      if (currentMapLayer !== 'satellite') {
        toggleMapLayer();
      } else {
        addBotMessage("🌍 Vous êtes déjà en mode satellite");
      }
    }
    
    else if (message.match(/carte standard|osm|openstreetmap|vue normale/i)) {
      if (currentMapLayer !== 'osm') {
        toggleMapLayer();
      } else {
        addBotMessage("🗺️ Vous êtes déjà en mode carte standard");
      }
    }

    // Aide et commandes
    else if (message.match(/aide|help|commandes|que faire|comment utiliser/i)) {
      addBotMessage(`❓ <strong>Commandes disponibles :</strong><br><br>
      • "Bonjour" - Message de bienvenue<br>
      • "Ligne X" - Infos sur une ligne<br>
      • "Toutes les lignes" - Liste complète<br>
      • "Horaires" - Horaires de service<br>
      • "Tarifs" - Prix des tickets<br>
      • "Station [nom]" - Info station<br>
      • "Itinéraire" - Planifier un trajet<br>
      • "Contact" - Coordonnées support<br>
      • "Satellite/Carte" - Changer de vue<br>
      • "Problème" - Support technique<br>
      • "Réseau" - Stats générales<br>
      • "Météo" - Conditions actuelles<br>
      • "Merci" - Remerciements`);
    }

    // Météo
    else if (message.match(/météo|temps|pluie|soleil|température/i)) {
      const weather = ["Ensoleillé 🌞", "Nuageux ☁️", "Pluvieux 🌧️", "Venteux 💨"];
      const randomWeather = weather[Math.floor(Math.random() * weather.length)];
      const temp = Math.floor(Math.random() * 15) + 20; // 20-35°C
      
      addBotMessage(`☀️ <strong>Météo du jour à Tunis</strong><br><br>
      • Conditions: ${randomWeather}<br>
      • Température: ${temp}°C<br>
      • Vent: ${Math.floor(Math.random() * 20)} km/h<br>
      • Humidité: ${Math.floor(Math.random() * 30) + 50}%<br><br>
      Bonne circulation !`);
    }

    // Remerciements
    else if (message.match(/merci|thanks|thank you|gracias/i)) {
      addBotMessage("😊 Je vous en prie ! N'hésitez pas si vous avez d'autres questions. Bon voyage avec Wasilni !");
    }

    // Au revoir
    else if (message.match(/au revoir|bye|à bientôt|ciao|adieu/i)) {
      addBotMessage("👋 Au revoir ! Passez une excellente journée. À bientôt sur Wasilni !");
    }

    // Réponse par défaut pour les questions non comprises
    else {
      addBotMessage(`🤔 Je n'ai pas bien compris votre question.<br><br>
      Pouvez-vous reformuler ou tapez <strong>"aide"</strong> pour voir la liste des commandes disponibles.<br><br>
      Exemples : "Ligne 5", "Horaires", "Tarifs", "Station X"`);
    }
    
  }, 1500); // Délai de 1.5 secondes pour simuler la réflexion
}

function sendMessage() {
  const input = document.getElementById('chatbotInput');
  const message = input.value.trim();
  
  if (message) {
    addUserMessage(message);
    input.value = '';
    processBotResponse(message);
  }
}

function sendSuggestion(text) {
  addUserMessage(text);
  document.getElementById('chatbotInput').value = '';
  processBotResponse(text);
}

function handleKeyPress(event) {
  if (event.key === 'Enter') {
    sendMessage();
  }
}

/* ================= INITIALISATION ================= */
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(() => {
    searchMap();
  }, 500);
  
  const searchInput = document.getElementById('searchInput');
  const parent = searchInput.parentNode;
  
  const wrapper = document.createElement('div');
  wrapper.className = 'position-relative';
  searchInput.parentNode.insertBefore(wrapper, searchInput);
  wrapper.appendChild(searchInput);
  
  searchInput.classList.add('pe-4');
  const clearBtn = document.createElement('span');
  clearBtn.innerHTML = '✕';
  clearBtn.style.cssText = 'position:absolute;right:10px;top:8px;cursor:pointer;color:#666;display:none;';
  clearBtn.onclick = clearSearch;
  wrapper.appendChild(clearBtn);
  
  searchInput.addEventListener('input', function() {
    clearBtn.style.display = this.value ? 'block' : 'none';
  });
  
  searchInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedLine) {
        zoomToLine(selectedLine);
      } else {
        const highlightedLines = [];
        lineLayer.getSource().getFeatures().forEach(f => {
          if (f.getStyle() === f.get("highlightStyle") || f.getStyle() === f.get("selectedStyle")) {
            highlightedLines.push(f.get('numero') || f.get('info').numero);
          }
        });
        if (highlightedLines.length > 0) {
          zoomToLine(highlightedLines[0]);
        }
      }
    }
  });
  
  searchInput.addEventListener('blur', function() {
    const value = this.value.toLowerCase().trim();
    if (value.startsWith('ligne ')) {
      const lineNum = value.replace('ligne ', '');
      const option = Array.from(document.getElementById('lineSelect').options)
        .find(opt => opt.value === lineNum);
      if (option) {
        document.getElementById('lineSelect').value = lineNum;
      }
    }
  });
});