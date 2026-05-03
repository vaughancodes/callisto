import { useEffect } from "react";

/**
 * Lock the page from scrolling while a modal/drawer is open. iOS Safari
 * ignores `overflow: hidden` on the body for touch scrolling, so this
 * also pins the body with `position: fixed` at the negative current
 * scroll offset and restores the prior position on close.
 *
 * Pass an `active` flag (defaults to true) so the hook works whether
 * the calling component is conditionally mounted or always mounted with
 * an `open` prop.
 *
 * If multiple lock-active components are mounted at once, the lock
 * stays held by the most recent caller; the saved scroll position is
 * tracked per-call so each cleanup restores correctly.
 */
let lockCount = 0;
let savedScrollY = 0;

function applyLock() {
  const body = document.body;
  body.dataset.scrollLockOverflow = body.style.overflow;
  body.dataset.scrollLockPosition = body.style.position;
  body.dataset.scrollLockTop = body.style.top;
  body.dataset.scrollLockLeft = body.style.left;
  body.dataset.scrollLockRight = body.style.right;
  body.dataset.scrollLockWidth = body.style.width;
  savedScrollY = window.scrollY;
  body.style.overflow = "hidden";
  body.style.position = "fixed";
  body.style.top = `-${savedScrollY}px`;
  body.style.left = "0";
  body.style.right = "0";
  body.style.width = "100%";
}

function releaseLock() {
  const body = document.body;
  body.style.overflow = body.dataset.scrollLockOverflow ?? "";
  body.style.position = body.dataset.scrollLockPosition ?? "";
  body.style.top = body.dataset.scrollLockTop ?? "";
  body.style.left = body.dataset.scrollLockLeft ?? "";
  body.style.right = body.dataset.scrollLockRight ?? "";
  body.style.width = body.dataset.scrollLockWidth ?? "";
  delete body.dataset.scrollLockOverflow;
  delete body.dataset.scrollLockPosition;
  delete body.dataset.scrollLockTop;
  delete body.dataset.scrollLockLeft;
  delete body.dataset.scrollLockRight;
  delete body.dataset.scrollLockWidth;
  window.scrollTo(0, savedScrollY);
}

export function useBodyScrollLock(active: boolean = true) {
  useEffect(() => {
    if (!active) return;
    if (lockCount === 0) applyLock();
    lockCount += 1;
    return () => {
      lockCount = Math.max(0, lockCount - 1);
      if (lockCount === 0) releaseLock();
    };
  }, [active]);
}

/**
 * Render-nothing component that locks body scroll for the duration of
 * its mount. Drop one inside any conditionally-rendered modal block to
 * freeze the underlying page while the modal is up.
 */
export function ScrollLock() {
  useBodyScrollLock(true);
  return null;
}
