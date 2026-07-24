"use client";

import { useEffect, useRef, useState } from "react";
import { Recommendation } from "@/lib/chat";
import { loadGoogleMaps } from "@/lib/maps-loader";

const DEFAULT_ZOOM = 13;

/**
 * Plots one marker per recommendation, labeled by rank, and fits the map
 * to their bounds. Uses the classic google.maps.Marker rather than
 * AdvancedMarkerElement -- Marker is deprecated (not removed) as of this
 * writing, but AdvancedMarkerElement needs its own "marker" library load
 * and, for some features, a Map ID; classic Marker keeps this step to one
 * script include with no extra Cloud Console setup beyond the domain-
 * restricted key. A reasonable later upgrade, not done here.
 */
export function RecommendationMap({ recommendations }: { recommendations: Recommendation[] }) {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadGoogleMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current || mapRef.current) return;
        mapRef.current = new google.maps.Map(mapDivRef.current, {
          center: { lat: recommendations[0]?.lat ?? 0, lng: recommendations[0]?.lng ?? 0 },
          zoom: DEFAULT_ZOOM,
        });
        renderMarkers();
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
    // Only ever needs to run once per mounted map instance -- this
    // component is created fresh per chat message (see app/chat/page.tsx),
    // so `recommendations` doesn't change out from under an already-loaded
    // map in normal use, but the effect below still keeps markers in sync
    // if it ever did.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mapRef.current) renderMarkers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommendations]);

  function renderMarkers() {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = recommendations.map(
      (r) =>
        new google.maps.Marker({
          map,
          position: { lat: r.lat, lng: r.lng },
          label: String(r.rank),
          title: r.name,
        })
    );

    if (recommendations.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      recommendations.forEach((r) => bounds.extend({ lat: r.lat, lng: r.lng }));
      map.fitBounds(bounds);
    }
  }

  if (recommendations.length === 0) return null;

  if (error) {
    return <p className="text-sm text-slate-400">Map unavailable: {error}</p>;
  }

  return <div ref={mapDivRef} className="h-64 w-full overflow-hidden rounded-lg border border-slate-200" />;
}
