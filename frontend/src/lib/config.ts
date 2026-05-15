export const config = {
  apiUrl:         process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  useMock:        process.env.NEXT_PUBLIC_USE_MOCK === "true",
  supabaseUrl:    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  allowedDomain:  process.env.NEXT_PUBLIC_ALLOWED_EMAIL_DOMAIN ?? "diu.edu.bd",
  appName:        process.env.NEXT_PUBLIC_APP_NAME ?? "yourDIU",
  enableCommunity: process.env.NEXT_PUBLIC_ENABLE_COMMUNITY !== "false",
} as const;
