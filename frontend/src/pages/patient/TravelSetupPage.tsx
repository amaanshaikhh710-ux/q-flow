import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  MapPin,
  Navigation,
  Car,
  Bike,
  Footprints,
  AlertCircle,
  Sparkles,
  Clock,
  ArrowRight,
  CheckCircle2,
  Search,
} from 'lucide-react';
import { travelApi, type ResolvedLocationItem } from '../../api/travel';
import { queueEntriesApi } from '../../api/queueEntries';
import { PageHeader } from '../../components/PageHeader';
import { extractErrorMessage } from '../../api/client';
import type { TravelMode } from '../../types/api';

const TRAVEL_MODES: {
  value: TravelMode;
  label: string;
  desc: string;
  icon: React.ReactNode;
}[] = [
  {
    value: 'DRIVE',
    label: 'Car / Driving',
    desc: 'Car, Cab, or Auto',
    icon: <Car className="w-5 h-5" />,
  },
  {
    value: 'TWO_WHEELER',
    label: 'Bike / Two-Wheeler',
    desc: 'Motorcycle or Scooter',
    icon: <Bike className="w-5 h-5" />,
  },
  {
    value: 'WALK',
    label: 'Walking',
    desc: 'On Foot',
    icon: <Footprints className="w-5 h-5" />,
  },
];

const QUICK_LANDMARKS = [
  { name: 'Mumbra', query: 'Mumbra' },
  { name: 'Thane West', query: 'Thane West' },
  { name: 'Dadar', query: 'Dadar' },
  { name: 'Vashi', query: 'Vashi' },
  { name: 'Kurla', query: 'Kurla' },
  { name: 'Andheri', query: 'Andheri' },
];

export default function TravelSetupPage() {
  const { entryId } = useParams<{ entryId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const isValidParam = Boolean(entryId && entryId !== ':entryId');

  // Input states
  const [addressQuery, setAddressQuery] = useState('');
  const [selectedLocation, setSelectedLocation] = useState<ResolvedLocationItem | null>(null);
  const [_searchResults, setSearchResults] = useState<ResolvedLocationItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [mode, setMode] = useState<TravelMode>('DRIVE');

  const [geoError, setGeoError] = useState<string | null>(null);
  const [geoSuccess, setGeoSuccess] = useState<string | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [calculationError, setCalculationError] = useState<string | null>(null);

  // 1. Fetch Entry & Hospital Details
  const { data: entry } = useQuery({
    queryKey: ['entry', entryId],
    queryFn: () => queueEntriesApi.getEntry(entryId!),
    enabled: isValidParam,
  });

  // 2. Fetch Latest Arrival Plan (if already calculated)
  const { data: arrivalPlan, refetch: refetchPlan } = useQuery({
    queryKey: ['arrival-plan', entryId],
    queryFn: () => travelApi.getArrivalPlan(entryId!),
    enabled: isValidParam,
    retry: false,
  });

  // Search address handler
  const handleSearchAddress = async (q: string) => {
    if (!q.trim() || q.trim().length < 2) return;
    setIsSearching(true);
    setGeoError(null);
    try {
      const res = await travelApi.resolveAddress(q.trim());
      setSearchResults(res.results || []);
      if (res.results && res.results.length > 0) {
        // Auto-select first if direct click from quick chip
        setSelectedLocation(res.results[0]);
      }
    } catch (err) {
      setGeoError('Unable to search address. Please try another area name.');
    } finally {
      setIsSearching(false);
    }
  };

  // Browser Geolocation (Optional)
  const detectLocation = () => {
    if (!navigator.geolocation) {
      setGeoError('Browser geolocation is not supported on this device. You can enter your area/address manually above.');
      return;
    }
    setIsDetecting(true);
    setGeoError(null);
    setGeoSuccess(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const item: ResolvedLocationItem = {
          name: 'Current Device Location',
          formatted_address: `Detected GPS (${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)})`,
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        };
        setSelectedLocation(item);
        setAddressQuery('Current Device Location');
        setGeoSuccess('Detected current GPS location successfully.');
        setIsDetecting(false);
      },
      (err) => {
        setIsDetecting(false);
        if (err.code === err.PERMISSION_DENIED) {
          setGeoError('Location permission was denied. You can enter your starting area/address manually without any issue.');
        } else {
          setGeoError('Device location is unavailable. Please enter your starting location manually.');
        }
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  // Mutation to switch active travel mode and recalculate departure
  const modeMutation = useMutation({
    mutationFn: async (newMode: TravelMode) => {
      return travelApi.setTravelMode(entryId!, newMode as any);
    },
    onSuccess: (updatedPlan) => {
      setMode((updatedPlan.selected_travel_mode as TravelMode) || 'DRIVE');
      void queryClient.invalidateQueries({ queryKey: ['arrival-plan', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
      refetchPlan();
    },
  });

  // Mutation to set origin and calculate travel
  const calculateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedLocation) {
        throw new Error('Please enter or select a starting location.');
      }
      return travelApi.setOrigin(entryId!, {
        latitude: selectedLocation.latitude,
        longitude: selectedLocation.longitude,
        travel_mode: mode,
        origin_address: selectedLocation.name,
      });
    },
    onSuccess: () => {
      setCalculationError(null);
      void queryClient.invalidateQueries({ queryKey: ['arrival-plan', entryId] });
      void queryClient.invalidateQueries({ queryKey: ['entry', entryId] });
      refetchPlan();
    },
    onError: (err) => {
      setCalculationError(extractErrorMessage(err));
    },
  });

  const handleCalculate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLocation) {
      if (addressQuery.trim()) {
        handleSearchAddress(addressQuery).then(() => {
          calculateMutation.mutate();
        });
        return;
      }
      setGeoError('Please enter your starting location (e.g. Mumbra, Dadar, Thane West).');
      return;
    }
    calculateMutation.mutate();
  };

  const isConfigRequired = arrivalPlan?.travel_status === 'CONFIGURATION_REQUIRED';
  const isAvailable = arrivalPlan?.travel_status === 'OPTIMIZED' && arrivalPlan.travel_duration_minutes != null;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <PageHeader
        title="Your Travel Plan & Leave Time"
        subtitle="Q-FLOW calculates real travel duration and tells you exactly when to depart so you arrive on time."
        backTo={isValidParam ? `/ticket/${entryId}` : '/dashboard'}
      />

      <main className="flex-1 max-w-xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6 animate-fade-up">
        {/* Form Card */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/90 shadow-sm space-y-6">
          <div className="flex items-center gap-3 p-4 rounded-2xl bg-blue-50/70 border border-blue-100 text-xs text-blue-900 leading-relaxed">
            <Sparkles className="w-5 h-5 text-blue-600 shrink-0" />
            <span>
              Enter your starting location to calculate real transit duration to the hospital and get your recommended departure time.
            </span>
          </div>

          <form onSubmit={handleCalculate} className="space-y-6">
            {/* Starting Location Input */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Starting Location (Where will you travel from?) <span className="text-rose-500">*</span>
              </label>

              <div className="flex gap-2">
                <div className="relative flex-1">
                  <MapPin className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                  <input
                    type="text"
                    required
                    placeholder="Enter your area (e.g. Mumbra, Thane West, Dadar, Vashi)..."
                    value={addressQuery}
                    onChange={(e) => {
                      setAddressQuery(e.target.value);
                      setSelectedLocation(null);
                    }}
                    onBlur={() => {
                      if (addressQuery.trim() && !selectedLocation) {
                        handleSearchAddress(addressQuery);
                      }
                    }}
                    className="w-full pl-10 pr-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <button
                  type="button"
                  disabled={isSearching}
                  onClick={() => handleSearchAddress(addressQuery)}
                  className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Search className="w-3.5 h-3.5" />
                  <span>{isSearching ? 'Finding...' : 'Search'}</span>
                </button>
              </div>

              {/* Quick Landmark Chips */}
              <div className="mt-3">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
                  Popular Landmarks
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_LANDMARKS.map((lm) => (
                    <button
                      key={lm.name}
                      type="button"
                      onClick={() => {
                        setAddressQuery(lm.query);
                        handleSearchAddress(lm.query);
                      }}
                      className="px-2.5 py-1 text-xs bg-slate-100 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 border border-slate-200 rounded-lg text-slate-700 transition-colors cursor-pointer"
                    >
                      {lm.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto-detected / Resolved Location Badge */}
              {selectedLocation && (
                <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold block">{selectedLocation.name}</span>
                    <span className="text-emerald-700">{selectedLocation.formatted_address}</span>
                  </div>
                </div>
              )}

              {/* Geolocation Button */}
              <div className="mt-3">
                <button
                  type="button"
                  disabled={isDetecting}
                  onClick={detectLocation}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition-colors border border-slate-200 cursor-pointer"
                >
                  <Navigation className={`w-3.5 h-3.5 text-blue-600 ${isDetecting ? 'animate-spin' : ''}`} />
                  <span>{isDetecting ? 'Detecting Device GPS...' : 'Use My Current Location (Browser GPS)'}</span>
                </button>
              </div>

              {geoSuccess && (
                <p className="mt-2 text-xs text-emerald-600 font-medium">{geoSuccess}</p>
              )}
              {geoError && (
                <div className="mt-2 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
                  <span>{geoError}</span>
                </div>
              )}
            </div>

            {/* Travel Mode Selector */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Travel Mode
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {TRAVEL_MODES.map((m) => {
                  const isSelected = mode === m.value;
                  return (
                    <button
                      key={m.value}
                      type="button"
                      onClick={() => setMode(m.value)}
                      className={`p-3 rounded-2xl border-2 text-center transition-all flex flex-col items-center justify-center gap-1.5 cursor-pointer ${
                        isSelected
                          ? 'border-blue-600 bg-blue-50 text-blue-900 font-bold shadow-xs'
                          : 'border-slate-200 bg-white hover:border-slate-300 text-slate-700'
                      }`}
                    >
                      <div className={isSelected ? 'text-blue-600' : 'text-slate-500'}>
                        {m.icon}
                      </div>
                      <span className="text-xs font-bold">{m.label}</span>
                      <span className="text-[10px] text-slate-400 block">{m.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {calculationError && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
                <span>{calculationError}</span>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={calculateMutation.isPending}
              className="w-full py-3.5 px-6 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {calculateMutation.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Calculating Route & Travel Time...</span>
                </>
              ) : (
                <>
                  <span>CALCULATE TRAVEL TIME & LEAVE-BY</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Departure Recommendation Card */}
        {arrivalPlan && (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/90 shadow-sm space-y-5 animate-fade-up">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-blue-600" />
                <h3 className="text-base font-bold text-slate-900">Your Recommended Departure Plan</h3>
              </div>
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Live Formula
              </span>
            </div>

            {/* If Google Routes not configured */}
            {isConfigRequired ? (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-900 text-xs space-y-2">
                <div className="flex items-center gap-2 font-bold">
                  <AlertCircle className="w-4 h-4 text-amber-600" />
                  <span>Travel calculation requires Google Maps configuration.</span>
                </div>
                <p className="text-amber-800 leading-relaxed">
                  The Google Routes API key has not yet been set in your environment. Q-FLOW never fabricates fake travel estimates. Once your key is configured, real-time driving, two-wheeler, and walking durations will calculate automatically.
                </p>
              </div>
            ) : isAvailable ? (
              <div className="space-y-5">
                {/* Real-time Calculation Header */}
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="font-semibold text-slate-700">Real-Time Routing Comparison</span>
                  <span className="text-[11px] text-emerald-700 font-bold bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                    Updated just now
                  </span>
                </div>

                {/* 3 Travel Modes Comparison: Walk, Bike, Car */}
                <div className="grid grid-cols-3 gap-2.5">
                  {/* Walk */}
                  <button
                    type="button"
                    onClick={() => modeMutation.mutate('WALK')}
                    disabled={modeMutation.isPending}
                    className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                      (arrivalPlan.selected_travel_mode || mode) === 'WALK'
                        ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                        : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1 font-bold text-xs">
                        <Footprints className="w-3.5 h-3.5 text-slate-600" />
                        <span>Walk</span>
                      </div>
                      {(arrivalPlan.selected_travel_mode || mode) === 'WALK' && (
                        <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                    <span className="text-base font-black text-slate-900 tracking-tight font-mono block">
                      {arrivalPlan.walking_duration_minutes != null ? `${arrivalPlan.walking_duration_minutes} min` : 'Unavailable'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      {arrivalPlan.walking_distance_meters ? `${(arrivalPlan.walking_distance_meters / 1000).toFixed(1)} km` : 'Footpath'}
                    </span>
                  </button>

                  {/* Bike / Two-Wheeler */}
                  <button
                    type="button"
                    onClick={() => modeMutation.mutate('TWO_WHEELER')}
                    disabled={modeMutation.isPending}
                    className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                      (arrivalPlan.selected_travel_mode || mode) === 'TWO_WHEELER'
                        ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                        : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1 font-bold text-xs">
                        <Bike className="w-3.5 h-3.5 text-blue-600" />
                        <span>Bike</span>
                      </div>
                      {(arrivalPlan.selected_travel_mode || mode) === 'TWO_WHEELER' && (
                        <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                    <span className="text-base font-black text-slate-900 tracking-tight font-mono block">
                      {arrivalPlan.bike_duration_minutes != null ? `${arrivalPlan.bike_duration_minutes} min` : 'Unavailable'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      {arrivalPlan.bike_distance_meters ? `${(arrivalPlan.bike_distance_meters / 1000).toFixed(1)} km` : 'Traffic-aware'}
                    </span>
                  </button>

                  {/* Car / Drive */}
                  <button
                    type="button"
                    onClick={() => modeMutation.mutate('DRIVE')}
                    disabled={modeMutation.isPending}
                    className={`p-3 rounded-2xl border-2 text-left transition-all cursor-pointer ${
                      (arrivalPlan.selected_travel_mode || mode) === 'DRIVE'
                        ? 'border-blue-600 bg-blue-50/70 text-blue-900 ring-2 ring-blue-100 shadow-xs'
                        : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1 font-bold text-xs">
                        <Car className="w-3.5 h-3.5 text-blue-600" />
                        <span>Car</span>
                      </div>
                      {(arrivalPlan.selected_travel_mode || mode) === 'DRIVE' && (
                        <div className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center">
                          <CheckCircle2 className="w-2.5 h-2.5" />
                        </div>
                      )}
                    </div>
                    <span className="text-base font-black text-slate-900 tracking-tight font-mono block">
                      {arrivalPlan.driving_duration_minutes != null ? `${arrivalPlan.driving_duration_minutes} min` : 'Unavailable'}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      {arrivalPlan.driving_distance_meters ? `${(arrivalPlan.driving_distance_meters / 1000).toFixed(1)} km` : 'Traffic-aware'}
                    </span>
                  </button>
                </div>

                {/* 3 Metric High-Impact Grid */}
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                      1. Estimated Turn
                    </span>
                    <span className="text-xl font-extrabold text-slate-900 font-mono mt-1 block">
                      {new Date(arrivalPlan.consultation_start_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">Doctor Ready</span>
                  </div>

                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                      2. Travel Time
                    </span>
                    <span className="text-xl font-extrabold text-blue-600 font-mono mt-1 block">
                      {arrivalPlan.travel_duration_minutes} min
                    </span>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">
                      {arrivalPlan.route_distance_meters ? `${(arrivalPlan.route_distance_meters / 1000).toFixed(1)} km` : 'Real Route'}
                    </span>
                  </div>

                  <div className="bg-emerald-50 p-4 rounded-2xl border border-emerald-200">
                    <span className="text-[10px] uppercase font-bold text-emerald-700 block tracking-wider">
                      3. Leave By
                    </span>
                    <span className="text-xl font-extrabold text-emerald-900 font-mono mt-1 block">
                      {arrivalPlan.departure_start_at
                        ? new Date(arrivalPlan.departure_start_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : 'On Time'}
                    </span>
                    <span className="text-[10px] text-emerald-700 font-semibold mt-0.5 block">
                      Includes {arrivalPlan.arrival_buffer_minutes || 15}m Buffer
                    </span>
                  </div>
                </div>

                {/* Calculation Breakdown & Formula */}
                <div className="p-4 bg-emerald-950 text-emerald-100 rounded-2xl border border-emerald-900 text-xs space-y-2">
                  <div className="flex items-center justify-between pb-1.5 border-b border-emerald-800">
                    <span className="font-bold text-white uppercase text-[10px] tracking-wider">
                      Q-FLOW Departure Formula
                    </span>
                    <span className="text-[10px] text-emerald-300">
                      Buffer: {arrivalPlan.arrival_buffer_minutes || 15} min
                    </span>
                  </div>
                  <div className="text-[11px] leading-relaxed space-y-1">
                    <p>
                      <strong className="text-white">Predicted Turn:</strong>{' '}
                      {new Date(arrivalPlan.consultation_start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    <p>
                      <strong className="text-white">Travel Duration:</strong>{' '}
                      {arrivalPlan.travel_duration_minutes} min (
                      {arrivalPlan.selected_travel_mode === 'TWO_WHEELER' ? 'Bike' : arrivalPlan.selected_travel_mode === 'WALK' ? 'Walking' : 'Car'}
                      )
                    </p>
                    <p>
                      <strong className="text-white">Arrival Buffer:</strong> {arrivalPlan.arrival_buffer_minutes || 15} min
                    </p>
                    <p className="pt-1 border-t border-emerald-800 text-emerald-200">
                      <strong className="text-white">Recommended Departure:</strong>{' '}
                      {arrivalPlan.departure_start_at
                        ? new Date(arrivalPlan.departure_start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : '—'}
                    </p>
                  </div>
                </div>

                {/* Clear Location Summary */}
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/70 text-xs text-slate-700 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Starting From:</span>
                    <span className="font-bold text-slate-900">{selectedLocation?.name || 'Your Origin'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Destination:</span>
                    <span className="font-bold text-slate-900">{(entry as any)?.hospital_name || 'Hospital Clinic'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Travel Mode:</span>
                    <span className="font-bold text-slate-900 capitalize">{(arrivalPlan.selected_travel_mode || mode).toLowerCase().replace('_', ' ')}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl text-slate-600 text-xs">
                Travel estimate unavailable. Please verify your origin location and route connectivity.
              </div>
            )}

            <div className="pt-2 flex gap-3">
              <button
                type="button"
                onClick={() => navigate(`/ticket/${entryId}`)}
                className="flex-1 py-3 px-4 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition-colors cursor-pointer text-center"
              >
                Return to Live Queue Ticket
              </button>
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="py-3 px-4 border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
              >
                My Appointments
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
