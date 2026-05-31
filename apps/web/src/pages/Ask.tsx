import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useBucket } from '../lib/BucketContext';
import type { QAResponse } from '../lib/types';

export default function Ask() {
  const { selectedBucketId, selectedBucket } = useBucket();
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<QAResponse | null>(null);

  const askMutation = useMutation({
    mutationFn: () => api.qa.ask(selectedBucketId!, question),
    onSuccess: (data) => setAnswer(data),
  });

  if (!selectedBucketId) {
    return <div className="text-center py-24 text-gray-500">Select or create a context bucket first.</div>;
  }

  return (
    <div className="space-y-8 animate-fadeIn max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
          Ask the graph
        </h1>
        <p className="text-sm text-gray-500 mt-2">
          Natural-language questions answered from <span className="font-semibold">{selectedBucket?.name}</span>'s knowledge graph.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
        <textarea
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What entities relate to X? How does A connect to B?"
          className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
        />
        <button
          onClick={() => askMutation.mutate()}
          disabled={question.trim().length < 3 || askMutation.isPending}
          className="mt-4 px-6 py-3 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 disabled:from-gray-300 disabled:to-gray-300 text-white font-semibold rounded-xl shadow-lg transition-all"
        >
          {askMutation.isPending ? 'Thinking…' : 'Ask'}
        </button>
        {askMutation.isError && (
          <p className="mt-3 text-sm text-red-700">{(askMutation.error as Error).message}</p>
        )}
      </div>

      {answer && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
            <h2 className="text-sm font-semibold text-indigo-700 uppercase mb-2">Answer</h2>
            <p className="text-gray-900 whitespace-pre-wrap leading-relaxed">{answer.answer}</p>
          </div>

          {answer.context.length > 0 && (
            <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">
                Evidence ({answer.context.length} relationships)
              </h2>
              <div className="space-y-2">
                {answer.context.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm flex-wrap">
                    <span className="px-2.5 py-1 rounded-md bg-blue-100 text-blue-800 font-medium">{t.source}</span>
                    <span className="text-gray-400">—{t.type.replace(/_/g, ' ')}→</span>
                    <span className="px-2.5 py-1 rounded-md bg-emerald-100 text-emerald-800 font-medium">{t.target}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
