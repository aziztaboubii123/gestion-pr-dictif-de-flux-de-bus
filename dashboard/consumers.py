import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Bus

class DashboardConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.accept()
        while True:
            buses = await self.get_buses()
            await self.send(text_data=json.dumps({
                'type': 'bus_locations',
                'buses': buses
        }))
        await asyncio.sleep(2)  # Toutes les 2 secondes

    @sync_to_async
    def get_buses(self):
        data = []
        for bus in Bus.objects.all():
            if bus.geometry:
                data.append({
                    "idBus": bus.idbus,
                    "immatriculation": bus.immatriculation,
                    "modele": bus.modele,
                    "statut": bus.statut,
                    "kilometrage": bus.kilometrage,
                    "idLigne": bus.idligne,
                    "lat": bus.geometry.y,
                    "lng": bus.geometry.x,
                })
        return data