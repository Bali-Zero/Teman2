import { useEffect, RefObject } from 'react';

/**
 * Hook to detect clicks outside of a referenced element
 *
 * @param ref - React ref object pointing to the element to monitor
 * @param handler - Callback function to execute when click outside is detected
 * @param enabled - Optional flag to enable/disable the listener (default: true)
 *
 * @example
 * ```tsx
 * const menuRef = useRef<HTMLDivElement>(null);
 * const [isOpen, setIsOpen] = useState(false);
 *
 * useClickOutside(menuRef, () => setIsOpen(false), isOpen);
 * ```
 */
export function useClickOutside<T extends HTMLElement = HTMLElement>(
  ref: RefObject<T | null>,
  handler: (event: MouseEvent) => void,
  enabled: boolean = true
): void {
  useEffect(() => {
    if (!enabled) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        handler(event);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [ref, handler, enabled]);
}

/**
 * Hook to detect clicks outside of multiple referenced elements
 * Useful when you have multiple menus/dropdowns that should close on outside click
 *
 * @param refs - Array of ref objects to monitor
 * @param handler - Callback function to execute when click outside all refs is detected
 * @param enabled - Optional flag to enable/disable the listener (default: true)
 *
 * @example
 * ```tsx
 * const menuRef = useRef<HTMLDivElement>(null);
 * const dropdownRef = useRef<HTMLDivElement>(null);
 *
 * useClickOutsideMultiple(
 *   [menuRef, dropdownRef],
 *   () => {
 *     setMenuOpen(false);
 *     setDropdownOpen(false);
 *   }
 * );
 * ```
 */
export function useClickOutsideMultiple<T extends HTMLElement = HTMLElement>(
  refs: RefObject<T | null>[],
  handler: (event: MouseEvent) => void,
  enabled: boolean = true
): void {
  useEffect(() => {
    if (!enabled) return;

    const handleClickOutside = (event: MouseEvent) => {
      const isOutsideAll = refs.every(
        (ref) => ref.current && !ref.current.contains(event.target as Node)
      );
      if (isOutsideAll) {
        handler(event);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [refs, handler, enabled]);
}
