import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Branch } from '../api/branches';

export default function AstanaMap({items, selected, onSelect}: {items: Branch[]; selected: string | null; onSelect: (id: string) => void}) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fit = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const [tilesUnavailable, setTilesUnavailable] = useState(false);
  useEffect(() => {
    if (!container.current) return;
    const map = L.map(container.current, {scrollWheelZoom: false, zoomControl: false}).setView([51.13, 71.42], 12);
    instance.current = map;
    L.control.zoom({position: 'bottomright'}).addTo(map);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, minZoom: 10, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tiles.on('tileerror', () => setTilesUnavailable(true));
    tiles.on('tileload', () => setTilesUnavailable(false));
    layer.current = L.layerGroup().addTo(map);
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container.current);
    return () => { observer.disconnect(); map.remove(); instance.current = null; layer.current = null; fit.current = false; };
  }, []);
  useEffect(() => {
    const map = instance.current, group = layer.current;
    if (!map || !group) return;
    group.clearLayers();
    items.forEach((b, i) => {
      const active = selected === b.id;
      const tone = b.shortage_days ? 'risk' : b.member_count ? 'staffed' : 'neutral';
      const marker = L.marker([b.lat, b.lon], {
        icon: L.divIcon({className: `branch-pin ${tone} ${active ? 'selected' : ''}`, html: `<span>${i + 1}</span>`, iconSize: [38, 46], iconAnchor: [19, 43]}),
        title: `Jana Post · ${b.address}`, alt: `Открыть филиал: ${b.address}`, zIndexOffset: active ? 1000 : 0,
      }).addTo(group);
      const tooltip = document.createElement('span');
      tooltip.textContent = `Jana Post · ${b.address}`;
      marker.bindTooltip(tooltip, {direction: 'top', offset: [0, -40]});
      marker.on('click', () => onSelectRef.current(b.id));
    });
    if (!fit.current && items.length) {
      map.fitBounds(L.latLngBounds(items.map(b => [b.lat, b.lon] as [number, number])), {padding: [48, 48], maxZoom: 13});
      fit.current = true;
    }
  }, [items, selected]);
  useEffect(() => {
    const b = items.find(item => item.id === selected);
    if (b && instance.current) instance.current.panTo([b.lat, b.lon], {animate: !window.matchMedia('(prefers-reduced-motion: reduce)').matches});
  }, [selected]);
  return <div className="astana-map-wrap">
    <div className="map-city-tag"><span className="live-dot" /> Астана <small>Jana Post</small></div>
    <div ref={container} className="astana-map" aria-label="Интерактивная карта филиалов Jana Post в Астане" />
    {tilesUnavailable && <div className="map-network-note" role="status">Подложка карты не загрузилась. Точки и список доступны; проверьте интернет.</div>}
    <div className="map-legend"><span><i className="legend-green" />Есть доступные вам сотрудники</span><span><i className="legend-gray" />Без сотрудников в вашей области доступа</span><span><i className="legend-orange" />Ниже минимума HR</span></div>
  </div>;
}
