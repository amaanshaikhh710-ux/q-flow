import { useNavigate } from 'react-router-dom';
import { HelpCircle, Home, ArrowLeft } from 'lucide-react';
import { PageHeader } from '../../components/PageHeader';

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <PageHeader showBack={false} />
      <main className="flex-1 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 p-8 text-center animate-fade-up">
          <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-4 text-blue-600">
            <HelpCircle className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 mb-2">Page Not Found</h1>
          <p className="text-sm text-slate-600 mb-6 leading-relaxed">
            The queue, doctor, or department page you are looking for might have expired, moved, or the link may be invalid.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => navigate(-1)}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-sm transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Go Back
            </button>
            <button
              onClick={() => navigate('/hospitals')}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition-colors shadow-sm"
            >
              <Home className="w-4 h-4" />
              Find Hospital
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
