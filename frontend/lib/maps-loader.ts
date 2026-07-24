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
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&loading=async`;
    script.async = true;
    script.onload = () => {
      // With loading=async, google.maps.Map / Marker / LatLngBounds
      // aren't populated on the legacy namespace just because the script
      // tag finished loading -- each one only appears after its library
      // is explicitly imported. Skipping this step is exactly what
      // produced "google.maps.Map is not a constructor" the first time
      // this ran against a real key.
      const googleNamespace = window.google;
      if (!googleNamespace?.maps?.importLibrary) {
        reject(new Error("Google Maps script loaded but google.maps.importLibrary is missing."));
        return;
      }
      Promise.all([googleNamespace.maps.importLibrary("maps"), googleNamespace.maps.importLibrary("marker")])
        .then(() => resolve())
        .catch(reject);
    };
    script.onerror = () => {
      loadPromise = null; // let a future call retry instead of rejecting forever
      reject(new Error("Failed to load the Google Maps script."));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}
