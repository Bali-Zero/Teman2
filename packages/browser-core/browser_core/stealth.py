"""Stealth plugins to avoid bot detection."""

from typing import List


class StealthPlugin:
    """Apply stealth patches to avoid bot detection."""

    @staticmethod
    def get_webdriver_patch() -> str:
        """Patch to hide webdriver property."""
        return """
        (() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        })()
        """

    @staticmethod
    def get_chrome_runtime_patch() -> str:
        """Patch to fix chrome runtime."""
        return """
        (() => {
            if (typeof window.chrome === 'undefined') {
                Object.defineProperty(window, 'chrome', {
                    value: { runtime: {} },
                    writable: true,
                    configurable: true,
                    enumerable: true,
                });
            } else if (typeof window.chrome.runtime === 'undefined') {
                window.chrome.runtime = {};
            }
        })()
        """

    @staticmethod
    def get_navigator_patch() -> str:
        """Patch navigator properties."""
        return """
        (() => {
            // Build a fake PluginArray-like object with length > 0
            const fakePlugins = {
                0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer',
                     description: 'Portable Document Format',
                     length: 1, item: (i) => ({}) },
                1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                     description: '', length: 1, item: (i) => ({}) },
                2: { name: 'Native Client', filename: 'internal-nacl-plugin',
                     description: '', length: 2, item: (i) => ({}) },
                length: 3,
                item: function(i) { return this[i] || null; },
                namedItem: function(name) {
                    for (let i = 0; i < this.length; i++) {
                        if (this[i].name === name) return this[i];
                    }
                    return null;
                },
                refresh: function() {},
                [Symbol.iterator]: function*() {
                    for (let i = 0; i < this.length; i++) yield this[i];
                }
            };
            Object.setPrototypeOf(fakePlugins, PluginArray.prototype);
            Object.defineProperty(navigator, 'plugins', {
                get: () => fakePlugins,
                configurable: true,
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true,
            });
        })()
        """

    @staticmethod
    def get_permissions_patch() -> str:
        """Patch permissions API."""
        return """
        (() => {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        })()
        """

    @staticmethod
    def get_canvas_noise_patch() -> str:
        """Add subtle noise to canvas fingerprint."""
        return """
        (() => {
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    // Add subtle noise
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] + (Math.random() < 0.5 ? -1 : 1);
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
        })()
        """

    @classmethod
    def get_all_scripts(cls) -> List[str]:
        """Get all stealth scripts."""
        return [
            cls.get_webdriver_patch(),
            cls.get_chrome_runtime_patch(),
            cls.get_navigator_patch(),
            cls.get_permissions_patch(),
            cls.get_canvas_noise_patch(),
        ]
