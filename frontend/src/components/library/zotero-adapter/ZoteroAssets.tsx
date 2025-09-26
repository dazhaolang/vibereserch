import { useEffect } from 'react';

interface Options {
  onReady?: () => void;
  injectScripts?: boolean;
}

const ZOTERO_CSS_ID = 'zotero-web-library-css';
const ZOTERO_SCRIPT_ID = 'zotero-web-library-js';

export function useZoteroAssets({ onReady, injectScripts = false }: Options = {}) {
  useEffect(() => {
    if (!document.getElementById(ZOTERO_CSS_ID)) {
      const link = document.createElement('link');
      link.id = ZOTERO_CSS_ID;
      link.rel = 'stylesheet';
      link.href = '/zotero/zotero-web-library.css';
      document.head.appendChild(link);
    }

    let script: HTMLScriptElement | null = null;
    if (injectScripts && !document.getElementById(ZOTERO_SCRIPT_ID)) {
      script = document.createElement('script');
      script.id = ZOTERO_SCRIPT_ID;
      script.src = '/zotero/zotero-web-library.js';
      script.async = false;
      document.body.appendChild(script);
    }

    onReady?.();

    return () => {
      if (script && script.parentElement) {
        script.parentElement.removeChild(script);
      }
    };
  }, [onReady, injectScripts]);
}
