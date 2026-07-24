// @types/google.maps types the global `google` namespace itself, but not
// every version declares it as a property on `Window` -- declared
// explicitly here so `window.google?.maps` (the "has the script tag
// finished loading yet" check in lib/maps-loader.ts) type-checks.
export {};

declare global {
  interface Window {
    google?: typeof google;
  }
}
