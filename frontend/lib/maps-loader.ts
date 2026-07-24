/**
 * Loads the Google Maps JavaScript API script exactly once, idempotently,
 * and resolves once window.google.maps is ready. A plain script-tag
 * loader rather than the @googlemaps/js-api-loader package -- one script
 * include doesn't need that package's extra machinery, and it's one
 * fewer dependency to install.
 *
 * The key here (NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) is DELIBERATELY separate
 * from the backend's GOOGLE_MAPS_API_KEY (backend/.env.example). The
 * backend's key is a server-side secret; this one is embedded in the
 * browser bundle by definition (every NEXT_PUBLIC_* var is), so it must
 * be a different key, restricted by HTTP referrer (Google Cloud Console >
 * Credentials > this key > Application restrictions > Websites) to only
 * the domains this app is actually served from, and API-restricted to
 * just "Maps JavaScript API" -- exactly the risk the design doc's own M5
 * entry calls out: "map/API key exposure -- ensure Maps JS key is
 * domain-restricted."
 */
let loadPromise: Promise<void> | null = null;

export function loadGoogleMaps(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("loadGoogleMaps can only run in the browser."));
  }
  if (loadPromise) {
    return loadPromise;
  }

  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  if (!apiKey) {
    return Promise.reject(
      new Error("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY is not set -- see frontend/.env.local.example.")
    );
  }

  loadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    // Deliberately the classic, eager-loading script -- no loading=async
    // param. That param switches Google's server to the newer "dynamic
    // library import" mode, but that mode only defines
    // google.maps.importLibrary if you also use Google's special inline
    // bootstrap snippet to set it up BEFORE fetching this script; a query
    // param alone on a plain <script src> doesn't do that. (Two real bugs
    // chased in testing: "google.maps.Map is not a constructor" trying to
    // use it without importLibrary, then "google.maps.importLibrary is
    // missing" trying to call importLibrary without the bootstrap
    // snippet.) The classic loader is simpler and sufficient here: it
    // populates google.maps.Map / Marker / LatLngBounds directly by the
    // time `onload` fires, no importLibrary call needed.
    // libraries=geometry (M6.7): needed for google.maps.geometry.encoding.decodePath,
    // which RecommendationMap uses to turn a route's encoded polyline back
    // into a drawable path. Unlike loading=async (see the comment above),
    // the libraries param has always worked with the classic loader --
    // it's a separate, older mechanism, not part of the dynamic-import
    // machinery that caused the two bugs documented above.
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      loadPromise = null; // let a future call retry instead of rejecting forever
      reject(new Error("Failed to load the Google Maps script."));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}
