import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Heart,
  Stethoscope,
  Activity,
  ChevronRight,
  FolderPlus,
  Sparkles,
} from 'lucide-react';
import { discoveryApi } from '../../api/discovery';
import { PageHeader } from '../../components/PageHeader';
import { SkeletonList } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { extractErrorMessage } from '../../api/client';
import type { DepartmentBrief } from '../../types/api';

function getDepartmentMeta(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes('cardio')) {
    return {
      icon: <Heart className="w-6 h-6 text-rose-600" />,
      bg: 'bg-rose-50 border-rose-200',
      description: 'Heart, vascular health & ECG monitoring',
      doctorCount: '2 Specialists',
      activeQueues: 'Active OPD',
    };
  }
  if (lower.includes('ortho') || lower.includes('bone')) {
    return {
      icon: <Activity className="w-6 h-6 text-teal-600" />,
      bg: 'bg-teal-50 border-teal-200',
      description: 'Bone, joint & musculoskeletal disorders',
      doctorCount: '2 Specialists',
      activeQueues: 'Active OPD',
    };
  }
  if (lower.includes('derma')) {
    return {
      icon: <Sparkles className="w-6 h-6 text-amber-600" />,
      bg: 'bg-amber-50 border-amber-200',
      description: 'Skin health, allergy & dermatological care',
      doctorCount: '1 Specialist',
      activeQueues: 'Active OPD',
    };
  }
  return {
    icon: <Stethoscope className="w-6 h-6 text-blue-600" />,
    bg: 'bg-blue-50 border-blue-200',
    description: 'Primary care, fever, diagnostics & chronic management',
    doctorCount: '2 Specialists',
    activeQueues: 'Active OPD',
  };
}

export default function DepartmentSelectPage() {
  const { hospitalId } = useParams<{ hospitalId: string }>();
  const navigate = useNavigate();

  const isValidParam = Boolean(hospitalId && hospitalId !== ':hospitalId');

  const {
    data: departments,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['departments', hospitalId],
    queryFn: () => discoveryApi.listDepartments(hospitalId!),
    enabled: isValidParam,
    staleTime: 60_000,
  });

  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <PageHeader title="Invalid Hospital" backTo="/hospitals" />
        <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8">
          <ErrorState
            title="Hospital Not Specified"
            message="Please select a valid hospital from the directory before choosing a department."
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
        title="Choose a department"
        subtitle="Select the medical specialty or department you want to visit."
        backTo="/hospitals"
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 animate-fade-up">
        {isLoading && <SkeletonList count={3} />}

        {isError && (
          <ErrorState
            title="Failed to Load Departments"
            message={extractErrorMessage(error)}
            onRetry={() => refetch()}
            backTo="/hospitals"
            backLabel="Choose Another Hospital"
          />
        )}

        {!isLoading && !isError && (!departments || departments.length === 0) && (
          <EmptyState
            icon={<FolderPlus className="w-8 h-8" />}
            title="No Departments Available"
            description="There are currently no active OPD departments registered under this hospital."
            action={
              <button
                type="button"
                onClick={() => navigate('/hospitals')}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800"
              >
                Choose Another Hospital
              </button>
            }
          />
        )}

        {!isLoading && !isError && departments && departments.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {departments.map((dept: DepartmentBrief) => {
              const meta = getDepartmentMeta(dept.name);
              return (
                <button
                  key={dept.id}
                  type="button"
                  onClick={() => navigate(`/doctors/${dept.id}?hospitalId=${hospitalId}`)}
                  className="w-full text-left bg-white hover:bg-slate-50/70 active:bg-slate-100/90 border border-slate-200/90 hover:border-blue-300 rounded-3xl p-6 shadow-xs hover:shadow-md transition-all flex items-center justify-between gap-4 group cursor-pointer"
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-2xl ${meta.bg} border flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform`}>
                      {meta.icon}
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                        {dept.name}
                      </h2>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        {meta.description}
                      </p>

                      <div className="flex items-center gap-2 mt-3">
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200/70">
                          {meta.doctorCount}
                        </span>
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span>{meta.activeQueues}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-slate-900 group-hover:text-white transition-all shrink-0">
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
