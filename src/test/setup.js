import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// jsdom no trae estas APIs del navegador; las usan gráficos, menús y el scroll.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}
if (!globalThis.IntersectionObserver) {
  globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } };
}
// (Las pruebas de contrato que corren en entorno "node" no tienen window ni Element.)
if (typeof window !== "undefined" && typeof Element !== "undefined") {
  if (!window.matchMedia) {
    window.matchMedia = (media) => ({
      matches: false, media, onchange: null,
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
    });
  }
  window.scrollTo = () => {};
  Element.prototype.scrollTo = () => {};
  Element.prototype.scrollIntoView = () => {};
}
