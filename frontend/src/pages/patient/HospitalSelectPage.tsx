import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Building2, MapPin, ChevronRight, Search, Hospital } from 'lucide-react';
import { discoveryApi } from '../../api/discovery';
import { PageHeader } from '../../components/PageHeader';
import { SkeletonList } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { extractErrorMessage } from '../../api/client';
import type { HospitalBrief } from '../../types/api';

export default function HospitalSelectPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const {
    data: hospitals,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['hospitals'],
    queryFn: discoveryApi.listHospitals,
    staleTime: 60_000,
  });

  const filteredHospitals = useMemo(() => {
    if (!hospitals) return [];
    if (!searchQuery.trim()) return hospitals;
    const q = searchQuery.toLowerCase();
    return hospitals.filter(
      (h) =>
        h.name.toLowerCase().includes(q) ||
        (h.address && h.address.toLowerCase().includes(q))
    );
  }, [hospitals, searchQuery]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <PageHeader
        title="Choose your hospital"
        subtitle="Find the OPD you want to visit."
        backTo="/"
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 animate-fade-up">
        {/* Search Input Bar */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search hospitals by name or location..."
              className="w-full pl-11 pr-4 py-3.5 rounded-2xl bg-white border border-slate-200/90 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all shadow-2xs"
            />
          </div>
        </div>

        {/* Loading State */}
        {isLoading && <SkeletonList count={3} />}

        {/* Error State */}
        {isError && (
          <ErrorState
            title="Failed to Load Hospitals"
            message={extractErrorMessage(error)}
            onRetry={() => refetch()}
            backTo="/"
            backLabel="Return Home"
          />
        )}

        {/* Empty State */}
        {!isLoading && !isError && filteredHospitals.length === 0 && (
          <EmptyState
            icon={<Hospital className="w-8 h-8" />}
            title={
              searchQuery.trim()
                ? 'No hospitals match your search'
                : 'No Registered Hospitals Found'
            }
            description={
              searchQuery.trim()
                ? 'Try searching with a different name or clear your search input.'
                : 'There are currently no active hospitals registered in the Q-FLOW system.'
            }
            action={
              searchQuery.trim() ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="text-sm font-semibold text-blue-600 hover:text-blue-700"
                >
                  Clear Search
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => refetch()}
                  className="px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800"
                >
                  Refresh Directory
                </button>
              )
            }
          />
        )}

        {/* Hospital Card List */}
        {!isLoading && !isError && filteredHospitals.length > 0 && (
          <div className="space-y-4">
            {filteredHospitals.map((hospital: HospitalBrief) => (
              <button
                key={hospital.id}
                type="button"
                onClick={() => navigate(`/departments/${hospital.id}`)}
                className="w-full text-left bg-white hover:bg-slate-50/70 active:bg-slate-100/90 border border-slate-200/90 hover:border-blue-300 rounded-3xl p-6 shadow-xs hover:shadow-md transition-all flex items-center justify-between gap-4 group cursor-pointer"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-700 flex items-center justify-center shrink-0 border border-slate-200 group-hover:bg-slate-900 group-hover:text-white transition-colors">
                    <Building2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                      {hospital.name}
                    </h2>
                    {hospital.address ? (
                      <p className="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
                        <MapPin className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                        <span>{hospital.address}</span>
                      </p>
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">Address registered</p>
                    )}

                    <div className="flex items-center gap-2 mt-3">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200/70">
                        3 departments
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        <span>OPD Available</span>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-slate-900 group-hover:text-white transition-all shrink-0">
                  <ChevronRight className="w-4 h-4" />
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
