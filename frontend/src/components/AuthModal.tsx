import React, { useState } from 'react';
import { loginUser, registerUser, upgradeAccount } from '../lib/api';
import type { UserProfile } from '../lib/types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [tab, setTab] = useState<'signin' | 'register' | 'upgrade'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [promoCode, setPromoCode] = useState('BHARAT_PRO_2026');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (tab === 'signin') {
        const res = await loginUser(email, password);
        onSuccess(res.user);
        onClose();
      } else if (tab === 'register') {
        const res = await registerUser(email, password, name, promoCode);
        onSuccess(res.user);
        onClose();
      } else if (tab === 'upgrade') {
        const res = await upgradeAccount(promoCode);
        onSuccess(res.user);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-zinc-950 border border-zinc-800 rounded w-full max-w-sm p-6 shadow-xl relative text-xs">
        <div className="flex items-baseline justify-between mb-4 border-b border-zinc-800 pb-3">
          <span className="font-semibold text-zinc-100 text-sm">Account</span>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 text-base leading-none"
          >
            &times;
          </button>
        </div>

        <div className="flex gap-4 mb-4 border-b border-zinc-850 pb-2">
          <button
            type="button"
            onClick={() => { setTab('signin'); setError(null); }}
            className={`transition-colors ${
              tab === 'signin' ? 'text-zinc-100 font-medium' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setTab('register'); setError(null); }}
            className={`transition-colors ${
              tab === 'register' ? 'text-zinc-100 font-medium' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Register
          </button>
          <button
            type="button"
            onClick={() => { setTab('upgrade'); setError(null); }}
            className={`transition-colors ${
              tab === 'upgrade' ? 'text-zinc-100 font-medium' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            Enterprise Upgrade
          </button>
        </div>

        {error && (
          <div className="mb-3 text-red-400 p-2 rounded bg-red-950/30 border border-red-900/50">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {tab === 'register' && (
            <div>
              <label className="block text-zinc-400 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 focus:outline-none focus:border-zinc-600"
              />
            </div>
          )}

          {tab !== 'upgrade' && (
            <>
              <div>
                <label className="block text-zinc-400 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 focus:outline-none focus:border-zinc-600"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 focus:outline-none focus:border-zinc-600"
                />
              </div>
            </>
          )}

          {(tab === 'register' || tab === 'upgrade') && (
            <div>
              <label className="block text-zinc-400 mb-1">Activation Code</label>
              <input
                type="text"
                value={promoCode}
                onChange={(e) => setPromoCode(e.target.value)}
                placeholder="BHARAT_PRO_2026"
                className="w-full px-2.5 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 font-mono focus:outline-none focus:border-zinc-600"
              />
            </div>
          )}

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1 text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-3.5 py-1 rounded bg-zinc-100 text-zinc-950 font-medium hover:bg-white disabled:opacity-50"
            >
              {loading ? '...' : tab === 'signin' ? 'Sign In' : tab === 'register' ? 'Register' : 'Upgrade'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
