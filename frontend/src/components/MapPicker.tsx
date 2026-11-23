"use client";

import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { Circle, MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";

export interface PickedLocation {
  lat: number;
  lng: number;
}

const pin = L.icon({
  iconUrl: markerIcon.src,
  iconRetinaUrl: markerIcon2x.src,
  shadowUrl: markerShadow.src,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const DEFAULT_CENTER: [number, number] = [39.9255, 32.8663]; // Ankara

function ClickCatcher({ onPick }: { onPick: (p: PickedLocation) => void }) {
  useMapEvents({
    click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }),
  });
  return null;
}

export default function MapPicker({ value, radius, onPick }: {
  value: PickedLocation | null;
  radius: number;
  onPick: (p: PickedLocation) => void;
}) {
  return (
    <MapContainer
      center={value ? [value.lat, value.lng] : DEFAULT_CENTER}
      zoom={13}
      className="h-full w-full rounded-xl"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> katkıcıları'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickCatcher onPick={onPick} />
      {value && (
        <>
          <Marker
            position={[value.lat, value.lng]}
            icon={pin}
            draggable
            eventHandlers={{ dragend: (e) => {
              const ll = (e.target as L.Marker).getLatLng();
              onPick({ lat: ll.lat, lng: ll.lng });
            } }}
          />
          <Circle
            center={[value.lat, value.lng]}
            radius={radius}
            pathOptions={{ color: "#24589a", weight: 1.5, fillOpacity: 0.08 }}
          />
        </>
      )}
    </MapContainer>
  );
}
