import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  historicalApi,
  type HistoricalAppointmentItem,
  type HistoricalFilterParams,
} from '../../api/historical';
import { discoveryApi, type StaffHospitalDetails } from '../../api/discovery';

export const StaffHistoricalReportsPage: React.FC = () => {
  const [hospitalInfo, setHospitalInfo] = useState<StaffHospitalDetails | null>(null);
  const [items, setItems] = useState<HistoricalAppointmentItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [exporting, setExporting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters state
  const [datePreset, setDatePreset] = useState<string>('this_week');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [departmentId, setDepartmentId] = useState<string>('');
  const [doctorId, setDoctorId] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [bookingSource, setBookingSource] = useState<string>('');

  useEffect(() => {
    fetchHospitalScope();
  }, []);

  useEffect(() => {
    fetchRecords(1);
  }, [datePreset]);

  const fetchHospitalScope = async () => {
    try {
      const data = await discoveryApi.getStaffHospital();
      setHospitalInfo(data);
    } catch (err: any) {
      console.error('Failed to load hospital scope', err);
    }
  };

  const buildFilterParams = (targetPage: number): HistoricalFilterParams => {
    const params: HistoricalFilterParams = {
      page: targetPage,
      page_size: 15,
    };

    if (datePreset) params.date_preset = datePreset;
    if (datePreset === 'custom') {
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();
    }
    if (departmentId) params.department_id = departmentId;
    if (doctorId) params.doctor_id = doctorId;
    if (status) params.status = status;
    if (bookingSource) params.booking_source = bookingSource;

    return params;
  };

  const fetchRecords = async (targetPage: number = 1) => {
    setLoading(true);
    setError(null);
    try {
      const params = buildFilterParams(targetPage);
      const res = await historicalApi.getAppointments(params);
      setItems(res.items);
      setTotalCount(res.total_count);
      setPage(res.page);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load historical records.');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    fetchRecords(1);
  };

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      const params = buildFilterParams(1);
      delete params.page;
      delete params.page_size;
      await historicalApi.downloadCsv(params);
    } catch (err: any) {
      alert('Failed to export CSV: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setExporting(false);
    }
  };

  // Doctors list for selected department or all departments derived from queues
  const availableDoctors = useMemo(() => {
    if (!hospitalInfo?.queues) return [];
    const filtered = departmentId
      ? hospitalInfo.queues.filter((q) => q.department_id === departmentId)
      : hospitalInfo.queues;
    const seen = new Set<string>();
    const docs: Array<{ id: string; name: string }> = [];
    for (const q of filtered) {
      if (q.doctor_id && !seen.has(q.doctor_id)) {
        seen.add(q.doctor_id);
        docs.push({ id: q.doctor_id, name: q.doctor_name });
      }
    }
    return docs;
  }, [hospitalInfo, departmentId]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header Navigation */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <Link
                to="/staff"
                className="text-sm px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition"
              >
                &larr; Back to Dashboard
              </Link>
              <span className="text-xs font-semibold uppercase px-2.5 py-1 bg-cyan-900/60 text-cyan-300 border border-cyan-700/50 rounded-md">
                {hospitalInfo ? hospitalInfo.hospital.name : 'Hospital Scope'}
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white mt-3">
              Historical OPD Reports & Data Export
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Audit past patient appointments, consultation durations, waiting times, and operational performance.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExportCsv}
              disabled={exporting || loading || items.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-sm transition"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {exporting ? 'Generating CSV...' : 'Export Filtered CSV'}
            </button>
          </div>
        </div>

        {/* Filter Bar Form */}
        <form
          onSubmit={handleApplyFilters}
          className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5 shadow-sm space-y-4"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {/* Date Preset */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Date Range Preset
              </label>
              <select
                value={datePreset}
                onChange={(e) => setDatePreset(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              >
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="this_week">This Week</option>
                <option value="last_week">Last Week</option>
                <option value="this_month">This Month</option>
                <option value="custom">Custom Date Range</option>
              </select>
            </div>

            {/* Department Filter */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Department / OPD
              </label>
              <select
                value={departmentId}
                onChange={(e) => {
                  setDepartmentId(e.target.value);
                  setDoctorId('');
                }}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              >
                <option value="">All Departments</option>
                {hospitalInfo?.departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Doctor Filter */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Doctor
              </label>
              <select
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              >
                <option value="">All Doctors</option>
                {availableDoctors.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Appointment Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="COMPLETED">Completed</option>
                <option value="NO_SHOW">No Show</option>
                <option value="WAITING">Waiting</option>
                <option value="IN_CONSULTATION">In Consultation</option>
                <option value="BOOKED">Booked (Pre-arrival)</option>
                <option value="ARRIVED">Arrived</option>
              </select>
            </div>

            {/* Booking Source Filter */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Booking Source
              </label>
              <select
                value={bookingSource}
                onChange={(e) => setBookingSource(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:outline-none"
              >
                <option value="">All Sources</option>
                <option value="ONLINE">Online</option>
                <option value="PHONE">Phone Booking</option>
                <option value="WALK_IN">Walk-in</option>
                <option value="STAFF">Staff Entry</option>
              </select>
            </div>

            {/* Submit Action */}
            <div className="flex items-end">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-2 px-4 rounded-lg text-sm transition shadow-sm"
              >
                {loading ? 'Filtering...' : 'Apply Filters'}
              </button>
            </div>
          </div>

          {/* Custom Date Pickers (Shown only if custom preset selected) */}
          {datePreset === 'custom' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-slate-700/50">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Custom Start Date & Time
                </label>
                <input
                  type="datetime-local"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Custom End Date & Time
                </label>
                <input
                  type="datetime-local"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500"
                />
              </div>
            </div>
          )}
        </form>

        {/* Error Alert */}
        {error && (
          <div className="bg-red-900/40 border border-red-700/60 text-red-200 p-4 rounded-xl text-sm">
            {error}
          </div>
        )}

        {/* Data Table */}
        <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-700/60 flex items-center justify-between text-xs text-slate-400">
            <span>
              Showing <strong>{items.length}</strong> of <strong>{totalCount}</strong> matching records
            </span>
            <span>Hospital-scoped data isolation enforced</span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-400 text-sm">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500 mb-3"></div>
              <p>Loading historical records...</p>
            </div>
          ) : items.length === 0 ? (
            <div className="p-12 text-center text-slate-400 text-sm">
              <p className="text-base font-semibold text-slate-300">No appointments found</p>
              <p className="mt-1">Try adjusting your date preset or filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/70 text-slate-300 border-b border-slate-700/60">
                    <th className="py-3 px-4 font-semibold">Token</th>
                    <th className="py-3 px-4 font-semibold">Date & Time</th>
                    <th className="py-3 px-4 font-semibold">Source</th>
                    <th className="py-3 px-4 font-semibold">Patient</th>
                    <th className="py-3 px-4 font-semibold">Department & Doctor</th>
                    <th className="py-3 px-4 font-semibold">Arrived</th>
                    <th className="py-3 px-4 font-semibold">Consultation</th>
                    <th className="py-3 px-4 font-semibold">Duration</th>
                    <th className="py-3 px-4 font-semibold">Wait Time</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/40">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-750 transition">
                      <td className="py-3 px-4 font-mono font-bold text-cyan-400 text-sm">
                        {item.token_display}
                      </td>
                      <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                        {new Date(item.date).toLocaleDateString()} <br />
                        <span className="text-slate-500 text-[11px]">
                          {new Date(item.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                            item.booking_source === 'ONLINE'
                              ? 'bg-blue-900/50 text-blue-300 border border-blue-700/40'
                              : item.booking_source === 'PHONE'
                              ? 'bg-purple-900/50 text-purple-300 border border-purple-700/40'
                              : item.booking_source === 'WALK_IN'
                              ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/40'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          {item.booking_source}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-200">
                        <div className="font-medium">{item.patient_name}</div>
                        {item.patient_phone && (
                          <div className="text-[11px] text-slate-400">{item.patient_phone}</div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        <div className="font-medium text-white">{item.doctor_name}</div>
                        <div className="text-[11px] text-slate-400">{item.department_name}</div>
                      </td>
                      <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                        {item.arrived_at ? (
                          new Date(item.arrived_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                        {item.consultation_started_at ? (
                          <>
                            {new Date(item.consultation_started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            {item.consultation_completed_at && (
                              <span className="text-slate-400">
                                {' '}
                                &rarr; {new Date(item.consultation_completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono">
                        {item.consultation_duration_minutes !== null && item.consultation_duration_minutes !== undefined ? (
                          <span className="text-emerald-400 font-medium">{item.consultation_duration_minutes} min</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono">
                        {item.waiting_time_minutes !== null && item.waiting_time_minutes !== undefined ? (
                          <span>{item.waiting_time_minutes} min</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                            item.status === 'COMPLETED'
                              ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50'
                              : item.status === 'IN_CONSULTATION'
                              ? 'bg-cyan-900/60 text-cyan-300 border border-cyan-700/50 animate-pulse'
                              : item.status === 'NO_SHOW'
                              ? 'bg-red-900/60 text-red-300 border border-red-700/50'
                              : item.status === 'WAITING'
                              ? 'bg-amber-900/60 text-amber-300 border border-amber-700/50'
                              : item.status === 'ARRIVED'
                              ? 'bg-blue-900/60 text-blue-300 border border-blue-700/50'
                              : 'bg-slate-700 text-slate-400'
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Footer */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-slate-700/60 flex items-center justify-between">
              <button
                onClick={() => fetchRecords(page - 1)}
                disabled={page <= 1 || loading}
                className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-xs font-semibold transition"
              >
                &larr; Previous
              </button>
              <span className="text-xs text-slate-400">
                Page <strong>{page}</strong> of <strong>{totalPages}</strong>
              </span>
              <button
                onClick={() => fetchRecords(page + 1)}
                disabled={page >= totalPages || loading}
                className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-xs font-semibold transition"
              >
                Next &rarr;
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
