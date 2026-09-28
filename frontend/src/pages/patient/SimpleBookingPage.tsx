import { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Building2,
  Stethoscope,
  User,
  Clock,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  MapPin,
  Calendar as CalendarIcon,
  ListOrdered,
  CalendarDays,
} from 'lucide-react';
import { discoveryApi } from '../../api/discovery';
import { schedulesApi } from '../../api/schedules';
import { queuesApi } from '../../api/queues';
import { BrandLogo } from '../../components/BrandLogo';
import { extractErrorMessage } from '../../api/client';
import type {
  HospitalBrief,
  DepartmentBrief,
  QueueEntryResponse,
  AvailableDoctorItem,
} from '../../types/api';

export default function SimpleBookingPage() {
  const navigate = useNavigate();

  // Wizard Step: 1 = Hospital, 2 = Department, 3 = Date, 4 = Doctor & Time, 5 = Confirm, 6 = Success
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5 | 6>(1);

  const [selectedHospital, setSelectedHospital] = useState<HospitalBrief | null>(null);
  const [selectedDepartment, setSelectedDepartment] = useState<DepartmentBrief | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [selectedDoctor, setSelectedDoctor] = useState<AvailableDoctorItem | null>(null);
  const [selectedTime, setSelectedTime] = useState<string>('');

  const [bookedEntry, setBookedEntry] = useState<QueueEntryResponse | null>(null);
  const [bookingError, setBookingError] = useState<string | null>(null);

  // Generate 14 upcoming dates for quick chips
  const upcomingDates = useMemo(() => {
    const dates = [];
    const now = new Date();
    for (let i = 0; i < 14; i++) {
      const d = new Date(now);
      d.setDate(now.getDate() + i);
      const iso = d.toISOString().split('T')[0];
      const isToday = i === 0;
      const isTomorrow = i === 1;
      const label = isToday
        ? 'Today'
        : isTomorrow
        ? 'Tomorrow'
        : d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
      dates.push({ iso, label, dayName: d.toLocaleDateString('en-US', { weekday: 'short' }), dayNum: d.getDate() });
    }
    return dates;
  }, []);

  // Query 1: Hospitals
  const { data: hospitals = [], isLoading: isLoadingHospitals } = useQuery({
    queryKey: ['discovery-hospitals'],
    queryFn: () => discoveryApi.listHospitals(),
  });

  // Query 2: Departments for selected hospital
  const { data: departments = [], isLoading: isLoadingDepartments } = useQuery({
    queryKey: ['discovery-departments', selectedHospital?.id],
    queryFn: () => discoveryApi.listDepartments(selectedHospital!.id),
    enabled: Boolean(selectedHospital),
  });

  // Query 3: ONLY available doctors scheduled for the selected hospital, department & date
  const {
    data: availableDoctorsData,
    isLoading: isLoadingDoctors,
  } = useQuery({
    queryKey: ['available-doctors', selectedHospital?.id, selectedDate, selectedDepartment?.id],
    queryFn: () =>
      schedulesApi.getAvailableDoctors(
        selectedHospital!.id,
        selectedDate,
        selectedDepartment?.id
      ),
    enabled: Boolean(selectedHospital && selectedDate && step >= 4),
  });

  const availableDoctors: AvailableDoctorItem[] = availableDoctorsData?.doctors || [];

  // Generate 30-min time slots within doctor's scheduled shift window
  const timeSlots = useMemo(() => {
    if (!selectedDoctor?.start_time || !selectedDoctor?.end_time) return [];
    const slots: { raw: string; label: string }[] = [];
    const [startH, startM] = selectedDoctor.start_time.split(':').map(Number);
    const [endH, endM] = selectedDoctor.end_time.split(':').map(Number);

    let curMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;

    while (curMinutes < endMinutes) {
      const h = Math.floor(curMinutes / 60);
      const m = curMinutes % 60;
      const raw = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`;
      const period = h >= 12 ? 'PM' : 'AM';
      const dispH = h % 12 || 12;
      const label = `${String(dispH).padStart(2, '0')}:${String(m).padStart(2, '0')} ${period}`;
      slots.push({ raw, label });
      curMinutes += 30;
    }
    return slots;
  }, [selectedDoctor]);

  // Booking Mutation
  const joinMutation = useMutation({
    mutationFn: async ({
      queueId,
      appointmentDate,
      appointmentTime,
    }: {
      queueId: string;
      appointmentDate: string;
      appointmentTime?: string;
    }) => {
      return queuesApi.join(queueId, appointmentDate, appointmentTime);
    },
    onSuccess: (data) => {
      setBookedEntry(data.entry);
      setStep(6); // Success screen
    },
    onError: (err) => {
      setBookingError(extractErrorMessage(err));
    },
  });

  const handleConfirmBooking = () => {
    if (!selectedDoctor?.queue_id) {
      setBookingError('No active queue available for this doctor schedule.');
      return;
    }
    if (!selectedDate) {
      setBookingError('Please choose an appointment date.');
      return;
    }
    setBookingError(null);
    joinMutation.mutate({
      queueId: selectedDoctor.queue_id,
      appointmentDate: selectedDate,
      appointmentTime: selectedTime || undefined,
    });
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="p-2 text-slate-400 hover:text-slate-700 rounded-lg transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <BrandLogo size="md" />
          </div>
          <Link
            to="/dashboard"
            className="text-sm font-semibold text-slate-500 hover:text-slate-800 transition-colors"
          >
            Cancel
          </Link>
        </div>
      </header>

      {/* Main Step Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8">
        {/* Step Indicator (Steps 1 to 5) */}
        {step < 6 && (
          <div className="mb-8">
            <div className="flex items-center justify-between max-w-2xl mx-auto mb-2 text-xs">
              <div className={`flex items-center gap-1 font-bold ${step >= 1 ? 'text-emerald-700' : 'text-slate-400'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step >= 1 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'}`}>1</span>
                <span>Hospital</span>
              </div>
              <div className={`h-0.5 flex-1 mx-1.5 ${step >= 2 ? 'bg-emerald-600' : 'bg-slate-200'}`} />
              <div className={`flex items-center gap-1 font-bold ${step >= 2 ? 'text-emerald-700' : 'text-slate-400'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step >= 2 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'}`}>2</span>
                <span>Department</span>
              </div>
              <div className={`h-0.5 flex-1 mx-1.5 ${step >= 3 ? 'bg-emerald-600' : 'bg-slate-200'}`} />
              <div className={`flex items-center gap-1 font-bold ${step >= 3 ? 'text-emerald-700' : 'text-slate-400'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step >= 3 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'}`}>3</span>
                <span>Date</span>
              </div>
              <div className={`h-0.5 flex-1 mx-1.5 ${step >= 4 ? 'bg-emerald-600' : 'bg-slate-200'}`} />
              <div className={`flex items-center gap-1 font-bold ${step >= 4 ? 'text-emerald-700' : 'text-slate-400'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step >= 4 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'}`}>4</span>
                <span>Doctor & Time</span>
              </div>
              <div className={`h-0.5 flex-1 mx-1.5 ${step >= 5 ? 'bg-emerald-600' : 'bg-slate-200'}`} />
              <div className={`flex items-center gap-1 font-bold ${step >= 5 ? 'text-emerald-700' : 'text-slate-400'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${step >= 5 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'}`}>5</span>
                <span>Confirm</span>
              </div>
            </div>
          </div>
        )}

        {/* STEP 1: Select Hospital */}
        {step === 1 && (
          <div>
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-slate-900">Select Hospital</h2>
              <p className="text-sm text-slate-500">Choose the healthcare facility you wish to visit</p>
            </div>

            {isLoadingHospitals ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-slate-500">Loading hospitals...</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {hospitals.map((hosp) => (
                  <div
                    key={hosp.id}
                    onClick={() => {
                      setSelectedHospital(hosp);
                      setSelectedDepartment(null);
                      setSelectedDoctor(null);
                      setStep(2);
                    }}
                    className={`p-6 rounded-2xl border-2 transition-all cursor-pointer bg-white hover:border-emerald-500 hover:shadow-md ${
                      selectedHospital?.id === hosp.id ? 'border-emerald-600 ring-2 ring-emerald-100' : 'border-slate-200'
                    }`}
                  >
                    <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4 font-bold">
                      <Building2 className="w-6 h-6" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mb-1">{hosp.name}</h3>
                    <p className="text-xs text-slate-500 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>{hosp.address || 'Address on file'}</span>
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STEP 2: Select Department */}
        {step === 2 && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-6">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wider block mb-1">
                {selectedHospital?.name}
              </span>
              <h2 className="text-2xl font-bold text-slate-900">Select Department</h2>
              <p className="text-sm text-slate-500">Choose the specialty or OPD clinic</p>
            </div>

            {isLoadingDepartments ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-slate-500">Loading departments...</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {departments.map((dept) => (
                    <div
                      key={dept.id}
                      onClick={() => {
                        setSelectedDepartment(dept);
                        setSelectedDoctor(null);
                        setStep(3);
                      }}
                      className={`p-5 rounded-2xl border-2 transition-all cursor-pointer bg-white hover:border-emerald-500 hover:shadow-md flex items-center gap-3.5 ${
                        selectedDepartment?.id === dept.id
                          ? 'border-emerald-600 ring-2 ring-emerald-100'
                          : 'border-slate-200'
                      }`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                        <Stethoscope className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">{dept.name}</h3>
                        <span className="text-[11px] text-slate-500">OPD Specialty</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-4">
                  <button
                    onClick={() => setStep(1)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    <span>Back to Hospitals</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* STEP 3: Choose Date */}
        {step === 3 && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-6">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wider block mb-1">
                {selectedHospital?.name} • {selectedDepartment?.name}
              </span>
              <h2 className="text-2xl font-bold text-slate-900">Choose Appointment Date</h2>
              <p className="text-sm text-slate-500">
                Select a date to view doctors scheduled and available for consultation
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm mb-6">
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
                Select from Upcoming Dates
              </label>

              {/* Quick Date Chips */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-6">
                {upcomingDates.slice(0, 8).map((d) => {
                  const isSelected = selectedDate === d.iso;
                  return (
                    <button
                      key={d.iso}
                      type="button"
                      onClick={() => setSelectedDate(d.iso)}
                      className={`p-3 rounded-xl border text-center transition-all cursor-pointer ${
                        isSelected
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-bold ring-2 ring-emerald-100'
                          : 'border-slate-200 hover:border-emerald-300 text-slate-700 bg-slate-50'
                      }`}
                    >
                      <span className="text-xs block text-slate-500">{d.dayName}</span>
                      <span className="text-lg font-extrabold block">{d.dayNum}</span>
                      <span className="text-[10px] text-slate-400 block">{d.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Manual Date Input */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-600">Or pick another date:</span>
                <input
                  type="date"
                  value={selectedDate}
                  min={new Date().toISOString().split('T')[0]}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-xl text-sm font-semibold text-slate-800 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setStep(2)}
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Departments</span>
              </button>

              <button
                disabled={!selectedDate}
                onClick={() => {
                  setSelectedDoctor(null);
                  setSelectedTime('');
                  setStep(4);
                }}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                <span>View Scheduled Doctors</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: Show ONLY Scheduled Available Doctors & Select Time Slot */}
        {step === 4 && (
          <div>
            <div className="text-center mb-6">
              <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wider block mb-1">
                {selectedHospital?.name} • {selectedDepartment?.name} •{' '}
                {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
                  weekday: 'short',
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
              <h2 className="text-2xl font-bold text-slate-900">Scheduled Doctors & Times</h2>
              <p className="text-sm text-slate-500">
                Only doctors scheduled by hospital staff for this date are available
              </p>
            </div>

            {isLoadingDoctors ? (
              <div className="p-12 text-center">
                <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-slate-500">Checking doctor schedules in database...</p>
              </div>
            ) : availableDoctors.length === 0 ? (
              <div className="max-w-lg mx-auto bg-white rounded-2xl border border-slate-200 p-8 text-center shadow-sm">
                <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-4">
                  <CalendarDays className="w-7 h-7" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">No Doctors Scheduled</h3>
                <p className="text-sm text-slate-600 mb-6">
                  No doctors from <strong className="text-slate-800">{selectedDepartment?.name}</strong> are scheduled
                  for consultation on{' '}
                  <span className="font-bold text-slate-800">
                    {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'short',
                    })}
                  </span>
                  . Doctors must be scheduled by hospital staff before patients can book.
                </p>
                <button
                  onClick={() => setStep(3)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold shadow-sm cursor-pointer"
                >
                  <CalendarIcon className="w-4 h-4" />
                  <span>Choose Another Date</span>
                </button>
              </div>
            ) : (
              <div className="space-y-6 max-w-2xl mx-auto">
                <div className="grid grid-cols-1 gap-4">
                  {availableDoctors.map((doc) => {
                    const isSelected = selectedDoctor?.doctor_id === doc.doctor_id;
                    return (
                      <div
                        key={doc.doctor_id}
                        onClick={() => {
                          setSelectedDoctor(doc);
                          setSelectedTime('');
                        }}
                        className={`p-5 rounded-2xl border-2 transition-all cursor-pointer bg-white hover:border-emerald-500 hover:shadow-md ${
                          isSelected ? 'border-emerald-600 ring-2 ring-emerald-100' : 'border-slate-200'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold shrink-0">
                              <User className="w-6 h-6" />
                            </div>
                            <div>
                              <h3 className="text-base font-bold text-slate-900">{doc.doctor_name}</h3>
                              <p className="text-xs text-emerald-700 font-semibold mb-2">{doc.department_name}</p>

                              {/* Scheduled Timing Display */}
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold">
                                <Clock className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Shift: {doc.formatted_time}</span>
                              </div>
                            </div>
                          </div>

                          <div className="text-right">
                            {isSelected ? (
                              <div className="w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                                <CheckCircle2 className="w-4 h-4" />
                              </div>
                            ) : (
                              <span className="text-xs font-semibold text-slate-400">Select</span>
                            )}
                            <div className="mt-2 text-xs text-slate-500">
                              {doc.total_waiting} in queue
                            </div>
                          </div>
                        </div>

                        {/* If doctor is selected, show time slot picker inside their shift */}
                        {isSelected && timeSlots.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-slate-100" onClick={(e) => e.stopPropagation()}>
                            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                              Select Appointment Slot:
                            </label>
                            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                              {timeSlots.map((slot) => {
                                const isSlotSelected = selectedTime === slot.raw;
                                return (
                                  <button
                                    key={slot.raw}
                                    type="button"
                                    onClick={() => setSelectedTime(slot.raw)}
                                    className={`py-1.5 px-2.5 rounded-lg border text-xs font-mono font-bold transition-all cursor-pointer text-center ${
                                      isSlotSelected
                                        ? 'border-emerald-600 bg-emerald-600 text-white shadow-xs'
                                        : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-emerald-400 hover:bg-emerald-50'
                                    }`}
                                  >
                                    {slot.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="mt-8 flex items-center justify-between pt-4 border-t border-slate-200">
                  <button
                    onClick={() => setStep(3)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    <span>Change Date</span>
                  </button>

                  <button
                    disabled={!selectedDoctor}
                    onClick={() => setStep(5)}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold shadow-sm transition-all disabled:opacity-50 cursor-pointer"
                  >
                    <span>Continue to Confirm</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* STEP 5: Review & Confirm */}
        {step === 5 && selectedDoctor && (
          <div className="max-w-xl mx-auto">
            <div className="text-center mb-6">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-3">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Confirm Your Appointment</h2>
              <p className="text-sm text-slate-500">Review your clinic, date, and doctor schedule below</p>
            </div>

            {bookingError && (
              <div className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0" />
                <span>{bookingError}</span>
              </div>
            )}

            <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6 shadow-sm space-y-4">
              <div className="flex items-start justify-between pb-4 border-b border-slate-100">
                <div>
                  <span className="text-xs text-slate-400 block uppercase font-bold tracking-wider">Hospital</span>
                  <span className="text-base font-bold text-slate-900">{selectedHospital?.name}</span>
                  <p className="text-xs text-slate-500">{selectedHospital?.address}</p>
                </div>
                <Building2 className="w-5 h-5 text-slate-400" />
              </div>

              <div className="flex items-start justify-between pb-4 border-b border-slate-100">
                <div>
                  <span className="text-xs text-slate-400 block uppercase font-bold tracking-wider">Department</span>
                  <span className="text-base font-bold text-slate-900">{selectedDoctor.department_name}</span>
                </div>
                <Stethoscope className="w-5 h-5 text-slate-400" />
              </div>

              <div className="flex items-start justify-between pb-4 border-b border-slate-100">
                <div>
                  <span className="text-xs text-slate-400 block uppercase font-bold tracking-wider">Consulting Doctor</span>
                  <span className="text-base font-bold text-slate-900">{selectedDoctor.doctor_name}</span>
                </div>
                <User className="w-5 h-5 text-slate-400" />
              </div>

              <div className="flex items-start justify-between pb-4 border-b border-slate-100">
                <div>
                  <span className="text-xs text-slate-400 block uppercase font-bold tracking-wider">Appointment Date</span>
                  <span className="text-base font-bold text-emerald-800">
                    {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
                      weekday: 'long',
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                    })}
                  </span>
                </div>
                <CalendarIcon className="w-5 h-5 text-emerald-600" />
              </div>

              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs text-slate-400 block uppercase font-bold tracking-wider">Scheduled Shift & Slot</span>
                  <span className="text-base font-bold text-emerald-700 block">
                    {selectedDoctor.formatted_time}
                  </span>
                  {selectedTime && (
                    <span className="text-xs font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded mt-1 inline-block">
                      Selected Slot: {selectedTime.slice(0, 5)}
                    </span>
                  )}
                  <p className="text-xs text-slate-500 mt-1">
                    {selectedDoctor.total_waiting} patients currently in queue
                  </p>
                </div>
                <Clock className="w-5 h-5 text-slate-400" />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setStep(4)}
                className="px-5 py-3 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
              >
                Back
              </button>

              <button
                onClick={handleConfirmBooking}
                disabled={joinMutation.isPending}
                className="flex-1 py-3 px-6 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {joinMutation.isPending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Allocating Token...</span>
                  </>
                ) : (
                  <>
                    <span>Confirm & Get Token</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* STEP 6: IMMEDIATE BOOKING CONFIRMATION */}
        {step === 6 && bookedEntry && (
          <div className="max-w-xl mx-auto animate-fade-up">
            <div className="bg-white rounded-3xl border border-emerald-200 shadow-xl p-8 text-center relative overflow-hidden">
              {/* Header Badge */}
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold uppercase tracking-wider mb-6">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>✓ APPOINTMENT BOOKED</span>
              </div>

              {/* Token Highlight Box */}
              <div className="bg-emerald-50/70 border border-emerald-200 rounded-2xl p-6 mb-8 max-w-sm mx-auto shadow-inner">
                <span className="text-xs uppercase font-bold text-emerald-700 tracking-wider block mb-1">
                  Your OPD Token Number
                </span>
                <span className="text-5xl font-black text-emerald-900 font-mono block mb-2 tracking-tight">
                  {bookedEntry.token_display}
                </span>
                <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-white text-emerald-800 border border-emerald-200 shadow-2xs">
                  Status: {bookedEntry.status}
                </span>
              </div>

              {/* Appointment Details Grid */}
              <div className="bg-slate-50 rounded-2xl p-5 mb-8 border border-slate-200 text-left space-y-3 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500 font-medium">Hospital</span>
                  <span className="font-bold text-slate-900">{selectedHospital?.name}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500 font-medium">Department</span>
                  <span className="font-bold text-slate-900">{selectedDoctor?.department_name}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500 font-medium">Consulting Doctor</span>
                  <span className="font-bold text-slate-900">{selectedDoctor?.doctor_name}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200/60">
                  <span className="text-slate-500 font-medium">Appointment Date</span>
                  <span className="font-bold text-emerald-800">
                    {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500 font-medium">Shift Timing</span>
                  <span className="font-bold text-emerald-700">
                    {selectedDoctor?.formatted_time}
                  </span>
                </div>
              </div>

              {/* Post-Booking Action Buttons */}
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => navigate(`/ticket/${bookedEntry.id}`)}
                  className="w-full py-3.5 px-6 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <ListOrdered className="w-4 h-4" />
                  <span>View Appointment</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  className="w-full py-3 px-6 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold text-sm transition-all cursor-pointer"
                >
                  <span>Go to My Appointments</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
