'use client';

import { useAutoAnimate as useAutoAnimateFormkit } from '@formkit/auto-animate/react';

/**
 * Re-export of useAutoAnimate from @formkit/auto-animate
 * Provides automatic animations for list add/remove/reorder operations
 *
 * Usage:
 * const [parent] = useAutoAnimate();
 * <ul ref={parent}>{items.map(item => <li key={item.id}>{item.name}</li>)}</ul>
 */
export const useAutoAnimate = useAutoAnimateFormkit;
export default useAutoAnimate;
