"use client";

import { useEffect, useRef, useState } from "react";
import { Recommendation } from "@/lib/chat";
import { loadGoogleMaps } from "@/lib/maps-loader";

const DEFAULT_ZOOM = 13;

// Cycled by rank for route polylines -- distinguishes candidates on the
// map the same way RecommendationList's rank badges distinguish them in
// the card list. Matches generate_route_candidates.py's MAX_CANDIDATES
// (5) so a full set of route results never repeats a color.
const ROUTE_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#d97706"];

/**
 * Plots one marker per point-based recommendation (fitness/workspace) and
 * one polyline per path-based recommendation (route, M6.7), fitting the
 * map to whichever combination is present. Weather results have neither
 * a point nor a path -- they never reach this component at all (see
 * app/chat/page.tsx, which renders WeatherTimeline for weather instead).
 *
 * Uses the classic google.maps.Marker rather than AdvancedMarkerElement --
 * Marker is deprecated (not removed) as of this writing, but
 * AdvancedMarkerElement needs its own "marker" library load and, for some
 * features, a Map ID; classic Marker keeps this step to one script
 * include with no extra Cloud Console setup beyond the domain-restricted
 * key. A reasonable later upgrade, not done here.
 */
export function RecommendationMap({ recommendations }: { recommendations: Recommendation[] }) {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
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

  // M6.7: route results have a polyline instead of a point -- same
  // typeof-narrowing defensiveness as plottable above, for the same
  // reason (stale localStorage history from before this field existed).
  const routable = recommendations.filter(
    (r): r is Recommendation & { polyline: string } => typeof r.polyline === "string" && r.polyline.length > 0
  );

  // Declared before the effects that call it (react-hooks/immutability
  // wants this -- function declarations are hoisted so it ran fine either
  // way, but the lint rule flags a function referenced inside an effect
  // being defined textually later in the component).
  function renderOverlays() {
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

    polylinesRef.current.forEach((line) => line.setMap(null));
    polylinesRef.current = routable.map(
      (r, i) =>
        new google.maps.Polyline({
          map,
          path: google.maps.geometry.encoding.decodePath(r.polyline),
          strokeColor: ROUTE_COLORS[i % ROUTE_COLORS.length],
          strokeOpacity: 0.85,
          strokeWeight: r.rank === 1 ? 5 : 3,
        })
    );

    const bounds = new google.maps.LatLngBounds();
    plottable.forEach((r) => bounds.extend({ lat: r.lat, lng: r.lng }));
    routable.forEach((r) => google.maps.geometry.encoding.decodePath(r.polyline).forEach((p) => bounds.extend(p)));
    if (plottable.length > 0 || routable.length > 0) {
      map.fitBounds(bounds);
    }
  }

  useEffect(() => {
    let cancelled = false;

    loadGoogleMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current || mapRef.current) return;
        // Center on the first point if there is one; otherwise fall back
        // to the first route's own start point (decoded from its
        // polyline) -- a route-only result (no plottable pins at all)
        // still needs somewhere sane to center before fitBounds takes
        // over in renderOverlays.
        const fallbackCenter = routable[0] ? google.maps.geometry.encoding.decodePath(routable[0].polyline)[0] : null;
        mapRef.current = new google.maps.Map(mapDivRef.current, {
          center: plottable[0]
            ? { lat: plottable[0].lat, lng: plottable[0].lng }
            : fallbackCenter ?? { lat: 0, lng: 0 },
          zoom: DEFAULT_ZOOM,
        });
        renderOverlays();
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
    // map in normal use, but the effect below still keeps overlays in sync
    // if it ever did.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mapRef.current) renderOverlays();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommendations]);

  if (plottable.length === 0 && routable.length === 0) return null;

  if (error) {
    return <p className="text-sm text-slate-400">Map unavailable: {error}</p>;
  }

  return <div ref={mapDivRef} className="h-64 w-full overflow-hidden rounded-lg border border-slate-200" />;
}
