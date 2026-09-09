// Execute the real publisher in isolation; cache/ISR behavior is NOT simulated.
export function unstable_cache<T>(callback: T): T { return callback; }
