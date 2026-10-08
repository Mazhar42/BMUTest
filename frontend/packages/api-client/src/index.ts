import createClient, { type Client, type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths } from "./schema";
export type Schemas = components["schemas"];

export interface ApiErrorBody {
  code: string;
  message_key: string;
  params: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly message_key: string;
  readonly params: Record<string, unknown>;

  constructor(status: number, body: Partial<ApiErrorBody> | undefined) {
    super(body?.code ?? `HTTP_${status}`);
    this.status = status;
    this.code = body?.code ?? (status === 0 ? "NETWORK" : `HTTP_${status}`);
    this.message_key = body?.message_key ?? (status === 0 ? "errors.network" : "errors.internal");
    this.params = body?.params ?? {};
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

export interface ApiOptions {
  baseUrl?: string;
  /** Returns the current bearer token (or null). May refresh first. */
  getToken: () => string | null | Promise<string | null>;
  onUnauthorized?: (code: string) => void;
  onLocked?: () => void;
}

export type Api = Client<paths>;

export function createApi(opts: ApiOptions): Api {
  const client = createClient<paths>({ baseUrl: opts.baseUrl ?? "", credentials: "include" });
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await opts.getToken();
      if (token && !request.headers.has("Authorization")) request.headers.set("Authorization", `Bearer ${token}`);
      request.headers.set("X-Requested-With", "bmu");
      return request;
    },
    async onResponse({ response }) {
      if (response.status === 401 || response.status === 423) {
        let code = "";
        try {
          code = ((await response.clone().json()) as Partial<ApiErrorBody>).code ?? "";
        } catch {
          /* not json */
        }
        if (response.status === 423 && code === "SESSION_LOCKED") opts.onLocked?.();
        else if (response.status === 401) opts.onUnauthorized?.(code);
      }
      return response;
    },
  };
  client.use(auth);
  return client;
}

/** Await an openapi-fetch call and return `data`, or throw a typed ApiError. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let res: { data?: T; error?: unknown; response: Response };
  try {
    res = await call;
  } catch {
    throw new ApiError(0, undefined);
  }
  if (!res.response.ok) throw new ApiError(res.response.status, res.error as Partial<ApiErrorBody> | undefined);
  return res.data as T;
}

async function errorFrom(res: Response): Promise<ApiError> {
  let body: Partial<ApiErrorBody> | undefined;
  try {
    body = (await res.json()) as Partial<ApiErrorBody>;
  } catch {
    body = undefined;
  }
  return new ApiError(res.status, body);
}

/** Fetch a binary (PDF, image) with the same auth and return an object URL. */
export async function fetchBlobUrl(url: string, token: string | null, init: RequestInit = {}): Promise<string> {
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), "X-Requested-With": "bmu" },
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, undefined);
  }
  if (!res.ok) throw await errorFrom(res);
  return URL.createObjectURL(await res.blob());
}

/** POST multipart/form-data (file uploads) with auth; returns the parsed JSON body or throws ApiError. */
export async function postForm<T>(url: string, form: FormData, token: string | null): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: form,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), "X-Requested-With": "bmu" },
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, undefined);
  }
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}
