/**
 * API Error Handler
 */

import { error as logError } from "@/lib/logger";

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function handleApiError(err: unknown): ApiError {
  if (err instanceof ApiError) {
    return err;
  }

  if (err instanceof Response) {
    const status = err.status;
    return new ApiError(getErrorMessage(status), status);
  }

  if (err instanceof Error) {
    logError("API Error:", err.message);
    return new ApiError(err.message, 0);
  }

  return new ApiError("An unexpected error occurred", 0);
}

function getErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return "Invalid request";
    case 401:
      return "Unauthorized";
    case 403:
      return "Forbidden";
    case 404:
      return "Resource not found";
    case 500:
      return "Server error";
    default:
      return "An error occurred";
  }
}

export async function safeFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      throw response;
    }

    return await response.json();
  } catch (err) {
    throw handleApiError(err);
  }
}
