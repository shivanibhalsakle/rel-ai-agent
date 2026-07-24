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

  // Defends against exactly the failure hit in testing: a thread
  // persisted to localStorage (M5.3) BEFORE lat/lng existed on
  // Recommendation still has old entries with those fields simply
  // missing, which threw "not a LatLng: in property lat: not a number"
  // straight out of the Marker/LatLngBounds constructors. Filtering here
  // means a page that's carrying stale pre-M5.5 history degrades to
  // "fewer pins" instead of a broken map for the whole message.
  //
  // As of M6, lat/lng are also legitimately null (not just historically
  // missing) for route/weather results -- typeof-narrowing before
  // Number.isFinite is now required, not just defensive, since
  // Number.isFinite's TS signature takes `number`, not `number | null`.
  const plottable = recommendations.filter(
    (r): r is Recommendation & { lat: number; lng: number } =>
      typeof r.lat === "number" && Number.isFinite(r.lat) && typeof r.lng === "number" && Number.isFinite(r.lng)
  );

  useEffect(() => {
    let cancelled = false;

    loadGoogleMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current || mapRef.current) return;
        mapRef.current = new google.maps.Map(mapDivRef.current, {
          center: { lat: plottable[0]?.lat ?? 0, lng: plottable[0]?.lng ?? 0 },
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
    markersRef.current = plottable.map(
      (r) =>
        new google.maps.Marker({
          map,
          position: { lat: r.lat, lng: r.lng },
          label: String(r.rank),
          title: r.name,
        })
    );

    if (plottable.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      plottable.forEach((r) => bounds.extend({ lat: r.lat, lng: r.lng }));
      map.fitBounds(bounds);
    }
  }

  if (plottable.length === 0) return null;

  if (error) {
    return <p className="text-sm text-slate-400">Map unavailable: {error}</p>;
  }

  return <div ref={mapDivRef} className="h-64 w-full overflow-hidden rounded-lg border border-slate-200" />;
}
