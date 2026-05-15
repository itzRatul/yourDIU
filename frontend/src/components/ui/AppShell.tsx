"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { useAuth } from "@/hooks/useAuth";
import { config } from "@/lib/config";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user && !config.useMock) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-diu-bg-base">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-diu-green flex items-center justify-center animate-pulse">
            <span className="text-white font-bold">D</span>
          </div>
          <p className="text-diu-text-dim text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user && !config.useMock) return null;

  return (
    <div className="flex min-h-screen bg-diu-bg-base">
      <Sidebar />
      <main className="flex-1 ml-56 min-h-screen">{children}</main>
    </div>
  );
}
