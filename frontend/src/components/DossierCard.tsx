import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { RagResultItem } from '../lib/types';

interface DossierCardProps {
  item: RagResultItem;
  isStreaming?: boolean;
}

export const DossierCard: React.FC<DossierCardProps> = ({ item, isStreaming = false }) => {
  return (
    <article className="border-t border-zinc-800/90 pt-8 space-y-6 animate-slide-up">
      <div className="flex items-baseline justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-zinc-200 tracking-tight">{item.ministry}</span>
          <span className="text-zinc-650">·</span>
          <span className="text-zinc-400 capitalize">{item.detail_level} Briefing</span>
          <span className="text-zinc-650">·</span>
          <span className="font-mono text-zinc-500">{item.reasoning_mode}</span>
          {isStreaming && (
            <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-amber-500/90 ml-2 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              Streaming tokens...
            </span>
          )}
        </div>
        {item.first_token_ms && (
          <span className="font-mono text-zinc-500 text-[11px]">
            {item.first_token_ms}ms TTFT
          </span>
        )}
      </div>

      <div className="text-zinc-200 text-[14px] leading-relaxed font-sans w-full selection:bg-amber-500/20">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p className="mb-3.5 last:mb-0 leading-relaxed text-zinc-300">{children}</p>,
            strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
            em: ({ children }) => <em className="italic text-zinc-300">{children}</em>,
            h1: ({ children }) => <h1 className="text-lg font-semibold text-zinc-100 mt-6 mb-3 pb-1 border-b border-zinc-850">{children}</h1>,
            h2: ({ children }) => <h2 className="text-base font-semibold text-zinc-100 mt-5 mb-2 pb-1 border-b border-zinc-850">{children}</h2>,
            h3: ({ children }) => <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-2">{children}</h3>,
            ul: ({ children }) => <ul className="list-disc list-outside pl-5 space-y-1.5 mb-3.5 text-zinc-300">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-outside pl-5 space-y-1.5 mb-3.5 text-zinc-300">{children}</ol>,
            li: ({ children }) => <li className="leading-relaxed">{children}</li>,
            table: ({ children }) => (
              <div className="w-full my-4 overflow-x-auto rounded border border-zinc-800 bg-zinc-950/70 shadow-xs">
                <table className="w-full text-xs text-left border-collapse">{children}</table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-zinc-900/90 text-zinc-200 font-medium border-b border-zinc-800">{children}</thead>
            ),
            th: ({ children }) => (
              <th className="px-3.5 py-2.5 font-semibold text-zinc-200 border-r border-zinc-850 last:border-r-0 whitespace-nowrap">{children}</th>
            ),
            tbody: ({ children }) => <tbody className="divide-y divide-zinc-850/70">{children}</tbody>,
            tr: ({ children }) => (
              <tr className="hover:bg-zinc-900/40 transition-colors">{children}</tr>
            ),
            td: ({ children }) => (
              <td className="px-3.5 py-2 border-r border-zinc-850/60 last:border-r-0 text-zinc-300 font-mono text-[12.5px]">{children}</td>
            ),
            code: ({ children, className }) => {
              const isInline = !className?.includes('language-');
              if (isInline) {
                return (
                  <code className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 font-mono text-[12px] text-amber-300/90">
                    {children}
                  </code>
                );
              }
              return (
                <pre className="p-3 my-3 rounded bg-zinc-950 border border-zinc-800/80 font-mono text-xs text-zinc-300 overflow-x-auto">
                  <code>{children}</code>
                </pre>
              );
            },
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-zinc-700 pl-3.5 my-3 text-zinc-400 italic">
                {children}
              </blockquote>
            ),
          }}
        >
          {item.answer}
        </ReactMarkdown>
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-1 bg-amber-500/80 animate-pulse align-middle" />
        )}
      </div>

      {item.sources && item.sources.length > 0 && (
        <div className="space-y-3 pt-3">
          <div className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-2">
            <span>Verified Citations ({item.sources.length})</span>
            <span className="h-px bg-zinc-850 flex-1"></span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 text-xs">
            {item.sources.map((s, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/95 hover:-translate-y-0.5 transition-all duration-200 group shadow-xs"
              >
                <div className="flex items-baseline justify-between gap-2 mb-1.5">
                  <span className="font-medium text-zinc-200 truncate group-hover:text-white transition-colors">
                    {s.title || 'Annual Report'}
                  </span>
                  {s.source_url && (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-500 group-hover:text-zinc-300 font-mono text-[11px] transition-colors"
                    >
                      Source ↗
                    </a>
                  )}
                </div>
                <div className="text-[11px] font-mono text-zinc-500">
                  Page {s.page ?? '—'} · {s.year || '2023-24'}
                  {s.section && ` · ${s.section}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {item.graph_context && (
        <details className="text-xs text-zinc-500 pt-2 group">
          <summary className="cursor-pointer hover:text-zinc-300 select-none font-mono transition-colors">
            View Graph Traversal Trace
          </summary>
          <pre className="mt-2 text-[11px] font-mono text-zinc-400 p-3 bg-zinc-950 rounded border border-zinc-900 overflow-x-auto whitespace-pre-wrap animate-fade-in">
            {item.graph_context}
          </pre>
        </details>
      )}
    </article>
  );
};
