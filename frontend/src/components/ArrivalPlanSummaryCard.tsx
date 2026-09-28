import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Navigation,
  Clock,
  Route,
  AlertCircle,
  Footprints,
  Car,
  Bike,
  Check,
  Search,
  MapPin,
  LocateFixed,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { ArrivalPlanResponse, TravelMode } from '../types/api';
import { travelApi, type ResolvedLocationItem } from '../api/travel';
import { formatTime } from '../utils/format';

interface ArrivalPlanSummaryCardProps {
  entryId: string;
  plan: ArrivalPlanResponse | null | undefined;
  isLoading?: boolean;
  className?: string;
}

const QUICK_LANDMARKS = [
  { name: 'Mumbra Railway Station', query: 'Mumbra Railway Station' },
  { name: 'Thane West', query: 'Thane West' },
  { name: 'Dadar', query: 'Dadar' },
  { name: 'Vashi', query: 'Vashi' },
  { name: 'Kurla', query: 'Kurla' },
  { name: 'Andheri', query: 'Andheri' },
];

function formatTravelDuration(minutes: number | null | undefined): string {
  if (minutes == null) return 'Unavailable';
  if (minutes >= 60) {
    const hrs = Math.floor(minutes / 60);
    const rem = minutes % 60;
    return rem > 0 ? `${hrs} hr ${rem} min` : `${hrs} hr`;
  }
  return `${minutes} min`;
}

function formatDistance(meters: number | null | undefined): string | null {
  if (meters == null) return null;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function ArrivalPlanSummaryCard({
  entryId,
  plan,
  isLoading = false,
  className = '',
}: ArrivalPlanSummaryCardProps) {
  const queryClient = useQueryClient();

  const isConfigRequired = plan?.travel_status === 'CONFIGURATION_REQUIRED';
  const hasConfiguredOrigin = Boolean(
    plan && (plan.departure_start_at || plan.origin_address || isConfigRequired)
  );
  const originAddress = plan?.origin_address || 'Configured Location';

  // Inline location editor state
  const [isEditingOrigin, setIsEditingOrigin] = useState<boolean>(!hasConfiguredOrigin);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ResolvedLocationItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [geoSuccess, setGeoSuccess] = useState<string | null>(null);

  const [activeMode, setActiveMode] = useState<string>(
    plan?.selected_travel_mode || 'DRIVE'
  );

  // Set travel origin mutation
  const originMutation = useMutation({
    mutationFn: async (params: {
      latitude: number;
      longitude: number;
      origin_address: string;
      travel_mode?: TravelMode;
    }) => {
      return travelApi.setOrigin(entryId, {
        latitude: params.latitude,
        longitude: params.longitude,
        origin_address: params.origin_address,
        travel_mode: (params.travel_mode || activeMode) as any,
      });
    },
    onSuccess: (updatedPlan) => {
      setIsEditingOrigin(false);
      setGeoError(null);
      setGeoSuccess(`Origin set to "${updatedPlan.origin_address || 'selected location'}"`);
      void queryClient.invalidateQueries({ queryKey: ['arrival-plan', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['patient-appointments'] });
    },
    onError: (err: any) => {
      setGeoError(err?.message || 'Failed to set starting origin. Please try again.');
    },
  });

  // Mode switch mutation
  const modeMutation = useMutation({
    mutationFn: async (newMode: 'DRIVE' | 'TWO_WHEELER' | 'WALK') => {
      return travelApi.setTravelMode(entryId, newMode);
    },
    onSuccess: (updatedPlan) => {
      setActiveMode(updatedPlan.selected_travel_mode || 'DRIVE');
      void queryClient.invalidateQueries({ queryKey: ['arrival-plan', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['patient-appointments'] });
    },
  });

  const handleModeChange = (newMode: 'DRIVE' | 'TWO_WHEELER' | 'WALK') => {
    if (newMode === activeMode || modeMutation.isPending) return;
    setActiveMode(newMode);
    modeMutation.mutate(newMode);
  };

  // Search address handler
  const handleSearch = async (queryToSearch?: string) => {
    const q = (queryToSearch ?? searchQuery).trim();
    if (!q) return;
    setIsSearching(true);
    setGeoError(null);
    setGeoSuccess(null);
    try {
      const res = await travelApi.resolveAddress(q);
      setSearchResults(res.results || []);
      if (res.results && res.results.length === 1) {
        // Auto-select if only 1 result
        selectLocation(res.results[0]);
      } else if (!res.results || res.results.length === 0) {
        setGeoError(`No locations found for "${q}". Please try a different landmark or area.`);
      }
    } catch (err) {
      setGeoError('Unable to search location. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  // Direct location selection
  const selectLocation = (loc: ResolvedLocationItem) => {
    setSearchResults([]);
    originMutation.mutate({
      latitude: loc.latitude,
      longitude: loc.longitude,
      origin_address: loc.formatted_address || loc.name,
      travel_mode: activeMode as TravelMode,
    });
  };

  // Browser Geolocation
  const handleDetectCurrentLocation = () => {
    if (!navigator.geolocation) {
      setGeoError('Browser geolocation is not supported on this device. Please type your location.');
      return;
    }
    setIsLocating(true);
    setGeoError(null);
    setGeoSuccess(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const formatted = `Current Device Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
        originMutation.mutate({
          latitude: lat,
          longitude: lng,
          origin_address: formatted,
          travel_mode: activeMode as TravelMode,
        });
      },
      (err) => {
        setIsLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError('Location permission was denied. Please type your starting area/address above.');
        } else {
          setGeoError('Unable to retrieve device location. Please search for your starting area manually.');
        }
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  if (isLoading) {
    return (
      <div className={`p-5 rounded-3xl bg-white border border-slate-200 animate-pulse space-y-4 ${className}`}>
        <div className="h-4 bg-slate-100 rounded w-1/3" />
        <div className="h-10 bg-slate-100 rounded w-2/3" />
        <div className="h-6 bg-slate-100 rounded w-1/2" />
      </div>
    );
  }

  // Durations & Distances
  const drivingDuration = plan?.driving_duration_minutes ?? plan?.travel_duration_minutes;
  const drivingDistStr = formatDistance(plan?.driving_distance_meters ?? plan?.route_distance_meters);
  const bikeDuration = plan?.bike_duration_minutes;
  const bikeDistStr = formatDistance(plan?.bike_distance_meters);
  const walkingDuration = plan?.walking_duration_minutes;
  const walkingDistStr = formatDistance(plan?.walking_distance_meters);

  const currentMode = plan?.selected_travel_mode || activeMode;
  const leaveByFormatted = plan?.departure_start_at ? formatTime(plan.departure_start_at) : 'Calculating...';

  const activeDurationMins =
    currentMode === 'TWO_WHEELER'
      ? bikeDuration
      : currentMode === 'WALK'
      ? walkingDuration
      : drivingDuration;

  return (
    <div className={`rounded-3xl p-6 bg-white border border-slate-200/90 shadow-2xs space-y-5 ${className}`}>
      {/* 1. Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-800">
          <Navigation className="w-4 h-4 text-blue-600" />
          <span>Travel & Arrival Engine</span>
        </div>
        <span
          className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border ${
            isConfigRequired
              ? 'bg-amber-50 text-amber-800 border-amber-300'
              : hasConfiguredOrigin
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}
        >
          {isConfigRequired
            ? 'Configuration Required'
            : hasConfiguredOrigin
            ? 'Google Routes Active'
            : 'Pending Location'}
        </span>
      </div>

      {/* 2. Active Starting Location Row & Toggle */}
      <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 text-xs space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
              Starting from:
            </span>
            <span className="font-bold text-slate-900 text-sm flex items-center gap-1.5 mt-0.5">
              <MapPin className="w-3.5 h-3.5 text-rose-500 shrink-0" />
              <span>{hasConfiguredOrigin ? originAddress : 'No origin set yet'}</span>
            </span>
          </div>

          <button
            type="button"
            onClick={() => setIsEditingOrigin(!isEditingOrigin)}
            className="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-blue-50 transition-colors cursor-pointer"
          >
            <span>{isEditingOrigin ? 'Close' : '[ Change Location ]'}</span>
            {isEditingOrigin ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Feedback alerts */}
        {geoSuccess && (
          <p className="text-[11px] text-emerald-700 font-semibold bg-emerald-50 p-2 rounded-lg border border-emerald-200">
            ✓ {geoSuccess}
          </p>
        )}
        {geoError && (
          <p className="text-[11px] text-rose-700 font-semibold bg-rose-50 p-2 rounded-lg border border-rose-200">
            {geoError}
          </p>
        )}
      </div>

      {/* 3. Inline Interactive Origin Picker (When open or not configured) */}
      {isEditingOrigin && (
        <div className="p-4 rounded-2xl bg-blue-50/50 border border-blue-100 space-y-3 animate-fade-in text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-800 flex items-center gap-1.5">
              <Route className="w-3.5 h-3.5 text-blue-600" />
              <span>Set Starting Location</span>
            </span>
            <span className="text-[10px] text-slate-500">Auto-routes to selected hospital</span>
          </div>

          {/* Option A: Search input */}
          <div className="space-y-1.5">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Enter starting area or station (e.g. Mumbra Railway Station)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      void handleSearch();
                    }
                  }}
                  className="w-full pl-8 pr-3 py-2 bg-white rounded-xl border border-slate-200 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button
                type="button"
                onClick={() => void handleSearch()}
                disabled={isSearching || !searchQuery.trim()}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-bold text-xs shadow-xs transition-colors cursor-pointer shrink-0"
              >
                {isSearching ? 'Searching...' : 'Search'}
              </button>
            </div>

            {/* Quick chips */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1">
              <span className="text-[10px] text-slate-500 font-semibold">Quick picks:</span>
              {QUICK_LANDMARKS.map((lm) => (
                <button
                  key={lm.name}
                  type="button"
                  onClick={() => {
                    setSearchQuery(lm.query);
                    void handleSearch(lm.query);
                  }}
                  className="px-2 py-0.5 rounded-full bg-white hover:bg-blue-100 text-slate-700 hover:text-blue-700 text-[10px] font-medium border border-slate-200 transition-colors cursor-pointer"
                >
                  {lm.name}
                </button>
              ))}
            </div>
          </div>

          {/* Search Results Dropdown */}
          {searchResults.length > 0 && (
            <div className="bg-white rounded-xl border border-blue-200 shadow-sm overflow-hidden divide-y divide-slate-100">
              <div className="px-3 py-1.5 bg-blue-50/80 text-[10px] font-bold text-blue-900">
                Select matching location:
              </div>
              {searchResults.map((loc, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => selectLocation(loc)}
                  disabled={originMutation.isPending}
                  className="w-full px-3 py-2 text-left hover:bg-blue-50/60 flex items-start gap-2 text-xs transition-colors cursor-pointer"
                >
                  <MapPin className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-900 block">{loc.name}</span>
                    <span className="text-[11px] text-slate-500 block">{loc.formatted_address}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-400">
            <div className="h-px flex-1 bg-slate-200" />
            <span>OR</span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          {/* Option B: Geolocation Button */}
          <button
            type="button"
            onClick={handleDetectCurrentLocation}
            disabled={isLocating || originMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-white hover:bg-slate-50 border border-slate-300 text-slate-800 rounded-xl font-bold text-xs shadow-xs transition-colors cursor-pointer"
          >
            <LocateFixed className={`w-3.5 h-3.5 text-blue-600 ${isLocating ? 'animate-spin' : ''}`} />
            <span>{isLocating ? 'Detecting GPS coordinates...' : 'Use My Current Location (Device GPS)'}</span>
          </button>
        </div>
      )}

      {/* 4. Configuration Required State (ZERO fake numbers) */}
      {isConfigRequired && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200/90 text-xs text-amber-900 space-y-2">
          <div className="flex items-center gap-2 font-bold">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Travel estimate unavailable — Google Maps routing configuration required.</span>
          </div>
          <p className="text-[11px] text-amber-800 leading-relaxed">
            Q-FLOW does not display fabricated travel times. To calculate real traffic-aware driving, bike, and walking routes, configure <code className="px-1 py-0.5 bg-amber-100 rounded text-amber-900 font-mono">GOOGLE_ROUTES_API_KEY</code> in your environment.
          </p>
        </div>
      )}

      {/* 5. Mode Selection Grid: 🚗 Car, 🏍️ Bike, 🚶 Walk */}
      {hasConfiguredOrigin && !isConfigRequired && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Select Your Travel Mode
            </span>
            {modeMutation.isPending && (
              <span className="text-[10px] font-semibold text-blue-600 animate-pulse">
                Recalculating departure...
              </span>
            )}
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            {/* Car / Drive */}
            <button
              type="button"
              onClick={() => handleModeChange('DRIVE')}
              disabled={modeMutation.isPending}
              className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                currentMode === 'DRIVE'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                  : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1 font-bold text-xs">
                  <Car className="w-3.5 h-3.5 text-blue-600" />
                  <span>Car</span>
                </div>
                {currentMode === 'DRIVE' && (
                  <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                    <Check className="w-2.5 h-2.5" />
                  </div>
                )}
              </div>
              <span className="text-lg font-black text-slate-900 tracking-tight font-mono block">
                {formatTravelDuration(drivingDuration)}
              </span>
              <span className="text-[10px] text-slate-500 block">
                {drivingDistStr || 'Traffic-aware'}
              </span>
            </button>

            {/* Bike / Two-Wheeler */}
            <button
              type="button"
              onClick={() => handleModeChange('TWO_WHEELER')}
              disabled={modeMutation.isPending}
              className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                currentMode === 'TWO_WHEELER'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                  : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1 font-bold text-xs">
                  <Bike className="w-3.5 h-3.5 text-blue-600" />
                  <span>Bike</span>
                </div>
                {currentMode === 'TWO_WHEELER' && (
                  <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                    <Check className="w-2.5 h-2.5" />
                  </div>
                )}
              </div>
              <span className="text-lg font-black text-slate-900 tracking-tight font-mono block">
                {formatTravelDuration(bikeDuration)}
              </span>
              <span className="text-[10px] text-slate-500 block">
                {bikeDistStr || 'Traffic-aware'}
              </span>
            </button>

            {/* Walk */}
            <button
              type="button"
              onClick={() => handleModeChange('WALK')}
              disabled={modeMutation.isPending}
              className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                currentMode === 'WALK'
                  ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                  : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1 font-bold text-xs">
                  <Footprints className="w-3.5 h-3.5 text-slate-600" />
                  <span>Walk</span>
                </div>
                {currentMode === 'WALK' && (
                  <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                    <Check className="w-2.5 h-2.5" />
                  </div>
                )}
              </div>
              <span className="text-lg font-black text-slate-900 tracking-tight font-mono block">
                {formatTravelDuration(walkingDuration)}
              </span>
              <span className="text-[10px] text-slate-500 block">
                {walkingDistStr || 'Footpath'}
              </span>
            </button>
          </div>

          {/* Google Routes Beta Advisory for Walk / Two-Wheeler */}
          {(currentMode === 'TWO_WHEELER' || currentMode === 'WALK') && (
            <div className="mt-2.5 px-3 py-2 rounded-xl bg-amber-50/80 border border-amber-200 text-[11px] text-amber-800 flex items-start gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
              <span>
                <strong>Route Advisory:</strong> Walking and two-wheeler directions are in beta. Use caution, as routes may lack dedicated footpaths or separate bicycle lanes. Always follow local traffic rules and signage.
              </span>
            </div>
          )}
        </div>
      )}

      {/* 6. Recommended Departure Card */}
      {hasConfiguredOrigin && !isConfigRequired && (
        <div className="p-5 rounded-2xl bg-emerald-950 text-white shadow-sm border border-emerald-900 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-emerald-400" />
              <span>RECOMMENDED DEPARTURE</span>
            </span>
            <span className="text-[10px] font-semibold text-emerald-400">
              {plan?.arrival_buffer_minutes || 15} min arrival buffer
            </span>
          </div>

          <div>
            <span className="text-xs text-emerald-200 block">
              Leave by ({currentMode === 'TWO_WHEELER' ? 'Bike' : currentMode === 'WALK' ? 'Walking' : 'Car'}):
            </span>
            <span className="text-3xl sm:text-4xl font-black text-white tracking-tight font-mono">
              {leaveByFormatted}
            </span>
          </div>

          <div className="pt-2.5 border-t border-emerald-900/80 text-[11px] text-emerald-200/90 leading-relaxed space-y-0.5">
            <p className="font-semibold text-white">Calculated Formula:</p>
            <ul className="list-disc list-inside space-y-0.5 text-emerald-200">
              <li>Predicted turn: {formatTime(plan?.consultation_start_at)}</li>
              <li>
                Real travel time: {formatTravelDuration(activeDurationMins)} (
                {currentMode === 'TWO_WHEELER' ? 'Bike' : currentMode === 'WALK' ? 'Walking' : 'Car'})
              </li>
              <li>Buffer before turn: {plan?.arrival_buffer_minutes || 15} min</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
