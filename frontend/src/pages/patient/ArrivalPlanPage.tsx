import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Clock,
  Navigation,
  ArrowRight,
  Info,
  MapPin,
  Sparkles,
  RefreshCw,
  Route,
} from 'lucide-react';
import { travelApi } from '../../api/travel';
import { PageHeader } from '../../components/PageHeader';
import { SkeletonCard } from '../../components/Skeleton';
import { ErrorState } from '../../components/ErrorState';
import { TravelStatusBadge } from '../../components/StatusIndicator';
import {
  formatTime,
  formatTimeWindow,
  formatDuration,
  formatDistance,
} from '../../utils/format';

export default function ArrivalPlanPage() {
  const { entryId } = useParams<{ entryId: string }>();

  const isValidParam = Boolean(entryId && entryId !== ':entryId');

  const {
    data: plan,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['arrival-plan', entryId],
    queryFn: () => travelApi.getArrivalPlan(entryId!),
    enabled: isValidParam,
    retry: 1,
  });

  if (!isValidParam) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        <PageHeader title="Invalid Ticket" backTo="/hospitals" />
        <main className="flex-1 max-w-lg w-full mx-auto px-4 py-8">
          <ErrorState
            title="Ticket Not Found"
            message="Please provide a valid ticket ID to view arrival recommendations."
            backTo="/hospitals"
            backLabel="Browse Hospitals"
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans pb-12">
      <PageHeader
        title="Arrival & Departure Plan"
        subtitle="Optimized recommendations based on travel time and queue velocity."
        backTo={`/ticket/${entryId}`}
      />

      <main className="flex-1 max-w-lg w-full mx-auto px-4 sm:px-6 py-6 space-y-4 animate-fade-up">
        {isLoading && (
          <div className="space-y-4">
            <SkeletonCard className="h-44" />
            <SkeletonCard className="h-36" />
          </div>
        )}

        {isError && (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 text-center space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
              <MapPin className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-slate-900">
              No Departure Plan Configured Yet
            </h2>
            <p className="text-xs text-slate-500 max-w-xs mx-auto leading-relaxed">
              Set your departure location and preferred transit mode to get an AI-recommended departure window.
            </p>
            <Link
              to={`/travel/${entryId}`}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs"
            >
              <span>Set Departure Location</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}

        {plan && (
          <>
            {/* Meaningful update alert */}
            {plan.is_meaningful_change && (
              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-3">
                <Sparkles className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block">Arrival Window Adjusted</span>
                  <span>
                    Your departure recommendation has been updated due to real-time doctor consultation pace changes.
                  </span>
                </div>
              </div>
            )}

            {/* 1. RECOMMENDED DEPARTURE WINDOW (HERO) */}
            <div className="rounded-3xl bg-blue-950 text-white p-6 sm:p-8 shadow-sm border border-blue-900 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-blue-200 text-xs font-semibold uppercase tracking-wider">
                  <Navigation className="w-4 h-4 text-blue-400" />
                  <span>Recommended Departure Window</span>
                </div>
                <TravelStatusBadge status={plan.travel_status} />
              </div>

              <div className="text-3xl sm:text-4xl font-black tracking-tight text-white">
                {plan.departure_start_at
                  ? formatTimeWindow(plan.departure_start_at, plan.departure_end_at)
                  : plan.travel_status === 'CONFIGURATION_REQUIRED'
                  ? 'Config Required'
                  : 'Pending Origin'}
              </div>

              <div className="pt-3 border-t border-blue-900/80 flex items-center justify-between text-xs text-blue-200">
                <span>Estimated Travel Time:</span>
                <span className="font-bold text-white text-sm">
                  {plan.travel_duration_minutes != null
                    ? `~${formatDuration(plan.travel_duration_minutes)}`
                    : plan.travel_status === 'CONFIGURATION_REQUIRED'
                    ? 'Unavailable (Config Required)'
                    : 'Pending Origin'}
                  {plan.travel_uncertainty_minutes != null && (
                    <span className="text-xs font-normal text-blue-300">
                      {' '}(±{plan.travel_uncertainty_minutes}m)
                    </span>
                  )}
                </span>
              </div>

              {/* Driving & Walking Breakdown */}
              {(plan.driving_duration_minutes != null || plan.walking_duration_minutes != null) && (
                <div className="pt-2 border-t border-blue-900/60 grid grid-cols-2 gap-2 text-xs text-blue-200">
                  <div>
                    <span className="text-[10px] text-blue-400 block uppercase font-semibold">Driving:</span>
                    <span className="font-bold text-white">
                      {plan.driving_duration_minutes != null ? `${plan.driving_duration_minutes} min` : 'Unavailable'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-blue-400 block uppercase font-semibold">Walking:</span>
                    <span className="font-bold text-white">
                      {plan.walking_duration_minutes != null ? formatDuration(plan.walking_duration_minutes) : 'Unavailable'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* 2. RECOMMENDED ARRIVAL AT HOSPITAL */}
            <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200 shadow-xs space-y-2">
              <div className="flex items-center gap-2 text-slate-500 text-xs font-bold uppercase tracking-wider">
                <Clock className="w-4 h-4 text-emerald-600" />
                <span>Recommended Hospital Arrival</span>
              </div>

              <div className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                {plan.arrival_start_at
                  ? formatTimeWindow(plan.arrival_start_at, plan.arrival_end_at)
                  : 'Pending Origin'}
              </div>

              <p className="text-xs text-slate-500 pt-1">
                Includes a comfortable {plan.arrival_buffer_minutes}-minute check-in buffer before your expected consultation window.
              </p>
            </div>

            {/* 3. CONSULTATION TARGET WINDOW */}
            <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200 shadow-xs space-y-2">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Target Consultation Window
              </h2>
              <div className="flex items-center gap-3 text-slate-900 font-bold text-lg">
                <span>{formatTime(plan.consultation_start_at)}</span>
                <ArrowRight className="w-4 h-4 text-slate-400" />
                <span>{formatTime(plan.consultation_end_at)}</span>
              </div>
              <p className="text-xs text-slate-500">
                Synchronized with the active doctor's consultation queue.
              </p>
            </div>

            {/* 4. ROUTE ACCURACY & EXPLANATION BANNER */}
            <div className="p-4 rounded-2xl bg-blue-50/60 border border-blue-100 flex items-start gap-2.5 text-xs text-slate-700 leading-relaxed">
              <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block text-slate-900 mb-0.5">
                  Based on your current consultation estimate and travel conditions.
                </span>
                <span>
                  {plan.explanation ||
                    'Calculated to ensure you bypass hospital waiting rooms and arrive right before your token is called.'}
                </span>
                {plan.route_distance_meters != null && (
                  <p className="mt-1 text-slate-500 font-medium">
                    Estimated Transit Distance: {formatDistance(plan.route_distance_meters)}
                  </p>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <Link
                to={`/travel/${entryId}`}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-3 min-h-[44px] rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs transition-colors border border-slate-200 cursor-pointer"
              >
                <Route className="w-4 h-4 text-slate-600" />
                <span>Update Origin</span>
              </Link>
              <button
                type="button"
                onClick={() => void refetch()}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-3 min-h-[44px] rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-800 font-semibold text-xs transition-colors border border-blue-200 cursor-pointer"
              >
                <RefreshCw className="w-4 h-4 text-blue-700" />
                <span>Refresh Route</span>
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
