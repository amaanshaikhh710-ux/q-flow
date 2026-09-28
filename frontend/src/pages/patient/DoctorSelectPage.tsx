import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { User, Calendar, ChevronRight } from 'lucide-react';
import { discoveryApi } from '../../api/discovery';
import { PageHeader } from '../../components/PageHeader';
import { SkeletonList } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { extractErrorMessage } from '../../api/client';
import { DoctorStatusBadge } from '../../components/StatusBadges';
import type { DoctorBrief } from '../../types/api';

export default function DoctorSelectPage() {
  const { departmentId } = useParams<{ departmentId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const hospitalId = searchParams.get('hospitalId');

  const isValidParam = Boolean(departmentId && departmentId !== ':departmentId');

  const {
    data: doctors,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['doctors', departmentId],
    queryFn: () => discoveryApi.listDoctors(departmentId!),
    enabled: isValidParam,
    staleTime: 60_000,
  });

  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <PageHeader title="Invalid Department" backTo="/hospitals" />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8">
          <ErrorState
            title="Department Not Specified"
            message="Please select a valid department before choosing a doctor."
            backTo="/hospitals"
            backLabel="Back to Hospitals"
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <PageHeader
        title="Select your doctor"
        subtitle="Choose a clinician for your outpatient consultation."
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 animate-fade-up">
        {isLoading && <SkeletonList count={3} />}

        {isError && (
          <ErrorState
            title="Failed to Load Doctors"
            message={extractErrorMessage(error)}
            onRetry={() => refetch()}
            backTo="/hospitals"
            backLabel="Back to Directory"
          />
        )}

        {!isLoading && !isError && (!doctors || doctors.length === 0) && (
          <EmptyState
            icon={<User className="w-8 h-8" />}
            title="No Doctors Available"
            description="There are currently no doctors scheduled under this department."
            action={
              <button
                type="button"
                onClick={() => navigate(-1)}
                className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700"
              >
                Choose Another Department
              </button>
            }
          />
        )}

        {!isLoading && !isError && doctors && doctors.length > 0 && (
          <div className="space-y-4">
            {doctors.map((doc: DoctorBrief) => {
              const initials = doc.name
                .replace(/^Dr\.\s*/i, '')
                .split(' ')
                .map((n) => n[0])
                .join('')
                .slice(0, 2)
                .toUpperCase();

              return (
                <div
                  key={doc.id}
                  className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs hover:shadow-xs transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100/80 text-blue-700 font-black text-lg flex items-center justify-center shrink-0 shadow-inner">
                      {initials || 'DR'}
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="text-base font-bold text-slate-900">
                          {doc.name}
                        </h2>
                        <DoctorStatusBadge status={doc.status} />
                      </div>

                      <p className="text-xs font-medium text-slate-600 mt-1">
                        Senior Attending Specialist • 10+ Years Clinical Experience
                      </p>

                      <div className="flex items-center gap-3 mt-2.5 text-xs text-slate-500">
                        <span className="inline-flex items-center gap-1 bg-slate-100 px-2.5 py-0.5 rounded-md font-mono text-[11px] text-slate-700">
                          Room 302 • OPD Wing
                        </span>
                        <span className="flex items-center gap-1 text-slate-400">
                          <Calendar className="w-3.5 h-3.5" />
                          Today's Queue Active
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => navigate(`/doctor-availability/${doc.id}?hospitalId=${hospitalId || ''}&departmentId=${departmentId}`)}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-all shadow-xs shrink-0 cursor-pointer"
                  >
                    <span>View availability</span>
                    <ChevronRight className="w-3.5 h-3.5 text-blue-400" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
