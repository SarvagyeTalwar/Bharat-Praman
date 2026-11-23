import React, { useState, useRef } from 'react';

export interface MinistryMeta {
  id: string;
  name: string;
  fullName: string;
  short: string;
  available: boolean;
  docCount?: number;
}

const AVAILABLE_MINISTRIES: MinistryMeta[] = [
  { id: 'education', name: 'Education', fullName: 'Ministry of Education', short: 'MoE', available: true, docCount: 12 },
  { id: 'finance', name: 'Finance', fullName: 'Ministry of Finance', short: 'MoF', available: true, docCount: 29 },
  { id: 'defence', name: 'Defence', fullName: 'Ministry of Defence', short: 'MoD', available: true, docCount: 5 },
  { id: 'home', name: 'Home Affairs', fullName: 'Ministry of Home Affairs', short: 'MHA', available: true, docCount: 3 },
];

const COMING_SOON_MINISTRIES: MinistryMeta[] = [
  { id: 'health', name: 'Health & Family Welfare', fullName: 'Ministry of Health & Family Welfare', short: 'MoHFW', available: false },
  { id: 'agriculture', name: 'Agriculture & Farmers Welfare', fullName: 'Ministry of Agriculture & Farmers Welfare', short: 'MoAFW', available: false },
  { id: 'road', name: 'Road Transport & Highways', fullName: 'Ministry of Road Transport & Highways', short: 'MoRTH', available: false },
  { id: 'rural', name: 'Rural Development', fullName: 'Ministry of Rural Development', short: 'MoRD', available: false },
  { id: 'railways', name: 'Railways', fullName: 'Ministry of Railways', short: 'MoR', available: false },
  { id: 'meity', name: 'Electronics & IT', fullName: 'Ministry of Electronics & Information Technology', short: 'MeitY', available: false },
  { id: 'mea', name: 'External Affairs', fullName: 'Ministry of External Affairs', short: 'MEA', available: false },
  { id: 'commerce', name: 'Commerce & Industry', fullName: 'Ministry of Commerce & Industry', short: 'MoCI', available: false },
  { id: 'power', name: 'Power & Energy', fullName: 'Ministry of Power & Renewable Energy', short: 'MoP', available: false },
];

interface MinistryFilterProps {
  selected: string;
  onChange: (id: string) => void;
}

export const MinistryFilter: React.FC<MinistryFilterProps> = ({ selected, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = window.setTimeout(() => {
      setIsOpen(false);
    }, 200);
  };

  const activeMinistry = AVAILABLE_MINISTRIES.find((m) => m.id === selected);

  return (
    <div className="relative">
      <div className="flex flex-wrap items-center gap-2">
        {/* All Ministries Dropdown Trigger with Hover Action */}
        <div
          className="relative inline-block"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <button
            type="button"
            onClick={() => {
              onChange('all');
              setIsOpen(!isOpen);
            }}
            className={`text-xs px-3 py-1.5 rounded flex items-center gap-1.5 transition-all duration-150 border ${
              selected === 'all'
                ? 'bg-zinc-100 text-zinc-950 font-medium border-zinc-100 shadow-xs'
                : 'bg-zinc-900/80 text-zinc-300 border-zinc-800 hover:border-zinc-700 hover:text-white'
            }`}
          >
            <span>All Ministries</span>
            <span className="text-[10px] text-zinc-500 font-mono">
              {isOpen ? '▲' : '▼'}
            </span>
          </button>

          {/* Hover Menu Popover */}
          {isOpen && (
            <div
              className="absolute left-0 top-full mt-1.5 w-[440px] max-w-[90vw] p-4 rounded-lg bg-zinc-950 border border-zinc-800 shadow-2xl z-50 animate-slide-up backdrop-blur-xl"
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
            >
              <div className="space-y-4">
                {/* Available Section */}
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 uppercase tracking-wider pb-2 border-b border-zinc-900">
                    <span className="flex items-center gap-1.5 text-zinc-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      Available Ministries
                    </span>
                    <span className="text-zinc-500">Ready to Query</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 pt-2">
                    {AVAILABLE_MINISTRIES.map((m) => {
                      const isSel = selected === m.id;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            onChange(m.id);
                            setIsOpen(false);
                          }}
                          className={`text-left p-2 rounded transition-all text-xs flex flex-col justify-between border ${
                            isSel
                              ? 'bg-zinc-900 border-zinc-700 text-white'
                              : 'bg-zinc-950 border-zinc-850 hover:bg-zinc-900 hover:border-zinc-700 text-zinc-300'
                          }`}
                        >
                          <div className="flex items-baseline justify-between w-full">
                            <span className="font-medium text-zinc-200">{m.name}</span>
                            <span className="text-[10px] font-mono text-zinc-500">{m.short}</span>
                          </div>
                          <span className="text-[10px] text-zinc-500 mt-0.5">
                            {m.docCount} Reports · 5 FYs
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Coming Soon Section */}
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 uppercase tracking-wider pb-2 border-b border-zinc-900">
                    <span className="flex items-center gap-1.5 text-zinc-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
                      More Ministries
                    </span>
                    <span className="text-zinc-500">Coming Soon</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 pt-2">
                    {COMING_SOON_MINISTRIES.map((m) => (
                      <div
                        key={m.id}
                        className="p-2 rounded bg-zinc-950/40 border border-zinc-900/60 text-xs flex items-center justify-between opacity-60 select-none cursor-not-allowed"
                        title="Document ingestion in progress"
                      >
                        <span className="text-zinc-400 truncate text-[11px]">{m.name}</span>
                        <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-zinc-900 text-zinc-500 border border-zinc-850 whitespace-nowrap">
                          Soon
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Quick-Access Pills for the 4 Active Ministries */}
        <div className="flex flex-wrap items-center gap-1.5">
          {AVAILABLE_MINISTRIES.map((m) => {
            const isActive = selected === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onChange(m.id)}
                className={`text-xs px-2.5 py-1 rounded transition-all duration-150 border ${
                  isActive
                    ? 'bg-zinc-100 text-zinc-950 font-medium border-zinc-100 shadow-xs'
                    : 'bg-zinc-950 border-zinc-850 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 hover:border-zinc-750'
                }`}
              >
                {m.name}
              </button>
            );
          })}
        </div>

        {/* Selected Ministry Detail Indicator */}
        {activeMinistry && (
          <span className="text-[11px] font-mono text-zinc-500 ml-1 hidden sm:inline animate-fade-in">
            Scoped to {activeMinistry.fullName} ({activeMinistry.docCount} reports)
          </span>
        )}
      </div>
    </div>
  );
};
