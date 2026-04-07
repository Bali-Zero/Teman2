"""Stealth plugins to avoid bot detection."""

from typing import List


class StealthPlugin:
    """Apply stealth patches to avoid bot detection."""

    @staticmethod
    def get_webdriver_patch() -> str:
        """Patch to hide webdriver property."""
        return """
        () => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        }
        """

    @staticmethod
    def get_chrome_runtime_patch() -> str:
        """Patch to fix chrome runtime."""
        return """
        () => {
            window.chrome = {
                runtime: {}
            };
        }
        """

    @staticmethod
    def get_navigator_patch() -> str:
        """Patch navigator properties."""
        return """
        () => {
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        }
        """

    @staticmethod
    def get_permissions_patch() -> str:
        """Patch permissions API."""
        return """
        () => {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        }
        """

    @staticmethod
    def get_canvas_noise_patch() -> str:
        """Add subtle noise to canvas fingerprint."""
        return """
        () => {
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
        }
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
