import React from 'react';
import type { UserProfile } from '../lib/types';

interface TopbarProps {
  user: UserProfile | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ user, onOpenAuth, onLogout }) => {
  return (
    <header className="border-b border-zinc-850 bg-zinc-950/90 sticky top-0 z-40 backdrop-blur-md transition-all duration-200">
      <div className="w-full px-6 md:px-10 lg:px-14 xl:px-16 h-13 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-amber-500/80 animate-radar"></div>
          <span className="font-semibold text-sm tracking-tight text-zinc-100 hover:text-white transition-colors cursor-pointer">
            Bharat Praman
          </span>
          <span className="text-zinc-700 select-none">/</span>
          <span className="text-xs text-zinc-400 font-mono tracking-tight hidden sm:inline">
            Fiscal &amp; Sovereign Intelligence
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          {user ? (
            <div className="flex items-center gap-3 animate-fade-in">
              <span className="text-zinc-300 font-medium">{user.name || user.email}</span>
              {user.tier === 'premium' ? (
                <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-700 font-medium">
                  PRO
                </span>
              ) : (
                <span className="font-mono text-[11px] text-zinc-500">Free</span>
              )}
              <button
                type="button"
                onClick={onLogout}
                className="text-zinc-500 hover:text-zinc-300 transition-colors ml-1"
              >
                Sign out
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onOpenAuth}
              className="text-zinc-400 hover:text-zinc-100 transition-colors duration-150 py-1 px-2 rounded hover:bg-zinc-900"
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
