"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { MapFeature } from "@/lib/api";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const recColors: Record<string, string> = {
  INVEST: "#10b981",
  HOLD: "#f59e0b",
  AVOID: "#ef4444",
};

interface LeafletMapProps {
  features: MapFeature[];
  selected: MapFeature | null;
  onSelect: (f: MapFeature) => void;
}

function createCircleMarker(f: MapFeature, map: L.Map, onSelect: (f: MapFeature) => void) {
  const color = recColors[f.recommendation] || "#888";
  const radius = 8 + (f.composite_score / 100) * 12;

  const icon = L.divIcon({
    className: "community-marker",
    html: `
      <div style="
        width: ${radius * 2}px;
        height: ${radius * 2}px;
        border-radius: 50%;
        background: ${color};
        border: 2px solid rgba(255,255,255,0.8);
        box-shadow: 0 0 ${radius}px ${color}60, 0 2px 8px rgba(0,0,0,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: ${Math.max(9, radius * 0.6)}px;
        font-weight: 700;
        color: white;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
      ">${f.composite_score.toFixed(0)}</div>
    `,
    iconSize: [radius * 2, radius * 2],
    iconAnchor: [radius, radius],
  });

  const marker = L.marker([f.lat, f.lng], { icon });

  const popupContent = `
    <div style="font-family: system-ui; min-width: 180px;">
      <div style="font-weight: 700; font-size: 14px; margin-bottom: 4px;">${f.community}</div>
      <div style="font-size: 12px; color: #888; margin-bottom: 8px;">${f.district}</div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px;">
        <div>
          <div style="color: #888;">Score</div>
          <div style="font-weight: 700; font-size: 16px;">${f.composite_score.toFixed(0)}<span style="font-size: 11px; color: #888;">/100</span></div>
        </div>
        <div>
          <div style="color: #888;">Net Yield</div>
          <div style="font-weight: 700; font-size: 16px; color: ${color};">${f.avg_net_yield.toFixed(1)}%</div>
        </div>
      </div>
      <div style="margin-top: 8px; padding: 4px 8px; border-radius: 6px; text-align: center; font-weight: 700; font-size: 12px; background: ${color}20; color: ${color};">
        ${f.recommendation}
      </div>
    </div>
  `;

  marker.bindPopup(popupContent, {
    className: "dark-popup",
    closeButton: false,
    maxWidth: 250,
  });

  marker.on("click", () => {
    const circleEl = marker.getElement()?.querySelector("div") as HTMLElement;
    if (circleEl) {
      circleEl.style.transform = "scale(1.3)";
      circleEl.style.boxShadow = `0 0 ${radius * 2}px ${color}90, 0 4px 16px rgba(0,0,0,0.5)`;
    }
    onSelect(f);
  });

  marker.on("mouseover", () => {
    const circleEl = marker.getElement()?.querySelector("div") as HTMLElement;
    if (circleEl) {
      circleEl.style.transform = "scale(1.15)";
    }
  });

  marker.on("mouseout", () => {
    const circleEl = marker.getElement()?.querySelector("div") as HTMLElement;
    if (circleEl) {
      circleEl.style.transform = "scale(1)";
      circleEl.style.boxShadow = `0 0 ${radius}px ${color}60, 0 2px 8px rgba(0,0,0,0.4)`;
    }
  });

  return marker;
}

export function LeafletMap({ features, selected, onSelect }: LeafletMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [25.2048, 55.2708],
      zoom: 11,
      zoomControl: false,
      attributionControl: false,
    });

    L.control.zoom({ position: "bottomright" }).addTo(map);

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 19,
      }
    ).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    features.forEach((f) => {
      const marker = createCircleMarker(f, map, (feat) => onSelectRef.current(feat));
      marker.addTo(map);
      markersRef.current.push(marker);
    });
  }, [features]);

  useEffect(() => {
    if (!selected) return;
    const map = mapInstanceRef.current;
    if (!map) return;

    map.flyTo([selected.lat, selected.lng], 13, { duration: 0.8 });

    markersRef.current.forEach((m) => {
      const mLatLng = m.getLatLng();
      if (
        Math.abs(mLatLng.lat - selected.lat) < 0.001 &&
        Math.abs(mLatLng.lng - selected.lng) < 0.001
      ) {
        m.openPopup();
      }
    });
  }, [selected]);

  return (
    <div
      ref={mapRef}
      className="w-full h-full rounded-lg"
      style={{ background: "#0a0a0a" }}
    />
  );
}
