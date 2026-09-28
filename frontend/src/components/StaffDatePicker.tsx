import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  isValidCanonicalDate,
  formatCanonicalDateDisplay,
  getHospitalTodayDateString,
  addDaysToCanonicalDate,
  parseCanonicalDateComponents,
  buildMonthCalendarGrid,
} from '../utils/dateUtils';

interface StaffDatePickerProps {
  /** Canonical date string YYYY-MM-DD */
  selectedDate: string;
  /** Callback fired when a valid canonical date is selected */
  onSelectDate: (canonicalDate: string) => void;
  className?: string;
  labelPrefix?: string;
}

export const StaffDatePicker: React.FC<StaffDatePickerProps> = ({
  selectedDate,
  onSelectDate,
  className = '',
  labelPrefix = 'QUEUE DATE:',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const todayStr = useMemo(() => getHospitalTodayDateString(), []);

  // Parse active date components for calendar view
  const activeComponents = useMemo(() => {
    const parsed = parseCanonicalDateComponents(selectedDate);
    if (parsed) return parsed;
    const todayParsed = parseCanonicalDateComponents(todayStr);
    return todayParsed || { year: 2026, month: 9, day: 22 };
  }, [selectedDate, todayStr]);

  // Calendar browsing month/year state
  const [viewYear, setViewYear] = useState<number>(activeComponents.year);
  const [viewMonth, setViewMonth] = useState<number>(activeComponents.month);

  // Sync browsing view when selectedDate changes externally
  useEffect(() => {
    if (activeComponents) {
      setViewYear(activeComponents.year);
      setViewMonth(activeComponents.month);
    }
  }, [activeComponents]);

  // Close calendar popover on outside click
  useEffect(() => {
    const handlePointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handlePointerDown);
    }
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
    };
  }, [isOpen]);

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const handlePrevMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (viewMonth === 1) {
      setViewYear((prev) => prev - 1);
      setViewMonth(12);
    } else {
      setViewMonth((prev) => prev - 1);
    }
  };

  const handleNextMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (viewMonth === 12) {
      setViewYear((prev) => prev + 1);
      setViewMonth(1);
    } else {
      setViewMonth((prev) => prev + 1);
    }
  };

  const handleSelectDay = (dateStr: string) => {
    if (isValidCanonicalDate(dateStr)) {
      onSelectDate(dateStr);
      setIsOpen(false);
    }
  };

  const calendarGrid = useMemo(() => {
    return buildMonthCalendarGrid(viewYear, viewMonth, selectedDate, todayStr);
  }, [viewYear, viewMonth, selectedDate, todayStr]);

  const quickPillDates = useMemo(() => {
    return [
      { label: 'Today', date: todayStr },
      { label: 'Tomorrow', date: addDaysToCanonicalDate(todayStr, 1) },
      { label: '22 Sep 2026', date: '2026-09-22' },
      { label: '23 Sep 2026', date: '2026-09-23' },
      { label: '24 Sep 2026', date: '2026-09-24' },
    ];
  }, [todayStr]);

  return (
    <div className={`relative inline-block ${className}`} ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        id="staff-date-picker-trigger"
        onClick={() => setIsOpen((prev) => !prev)}
        className="inline-flex items-center gap-2 bg-blue-50/90 hover:bg-blue-100/90 active:bg-blue-200/90 px-3 py-1.5 rounded-xl border border-blue-200/90 text-blue-950 font-bold transition-all shadow-2xs cursor-pointer select-none"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        <Calendar className="w-4 h-4 text-blue-600 shrink-0" />
        <span className="text-[11px] uppercase tracking-wider text-blue-800">{labelPrefix}</span>
        <span className="text-xs font-black text-blue-950">
          {formatCanonicalDateDisplay(selectedDate, 'long')}
        </span>
      </button>

      {/* Popover Calendar */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Queue Date Selector"
          className="absolute left-0 mt-2 z-50 w-72 sm:w-80 bg-white rounded-2xl border border-slate-200 shadow-xl p-4 text-slate-800 animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Calendar Month Navigation Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <button
              type="button"
              onClick={handlePrevMonth}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors"
              title="Previous Month"
              aria-label="Previous Month"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <span className="text-sm font-bold text-slate-900 tracking-tight">
              {monthNames[viewMonth - 1]} {viewYear}
            </span>

            <button
              type="button"
              onClick={handleNextMonth}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors"
              title="Next Month"
              aria-label="Next Month"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Quick Date Shortcuts */}
          <div className="py-2.5 flex items-center gap-1.5 flex-wrap border-b border-slate-100">
            {quickPillDates.map((pill) => {
              const isPillSelected = pill.date === selectedDate;
              return (
                <button
                  key={pill.label}
                  type="button"
                  onClick={() => {
                    handleSelectDay(pill.date);
                    const p = parseCanonicalDateComponents(pill.date);
                    if (p) {
                      setViewYear(p.year);
                      setViewMonth(p.month);
                    }
                  }}
                  className={`px-2 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer ${
                    isPillSelected
                      ? 'bg-blue-600 text-white shadow-2xs'
                      : 'bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-600 border border-slate-200/60'
                  }`}
                >
                  {pill.label}
                </button>
              );
            })}
          </div>

          {/* Weekday Header */}
          <div className="grid grid-cols-7 gap-1 pt-3 pb-1 text-center">
            {['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].map((d) => (
              <span key={d} className="text-[10px] font-bold uppercase text-slate-400">
                {d}
              </span>
            ))}
          </div>

          {/* Days Grid */}
          <div className="grid grid-cols-7 gap-1 text-center">
            {calendarGrid.map((item, idx) => {
              return (
                <button
                  key={`${item.dateStr}-${idx}`}
                  type="button"
                  onClick={() => handleSelectDay(item.dateStr)}
                  className={`h-8 w-full rounded-xl text-xs font-semibold flex items-center justify-center transition-all cursor-pointer ${
                    item.isSelected
                      ? 'bg-blue-600 text-white font-black shadow-xs ring-2 ring-blue-300'
                      : item.isToday
                      ? 'bg-blue-50 text-blue-700 font-bold border border-blue-300'
                      : item.isCurrentMonth
                      ? 'hover:bg-slate-100 text-slate-800'
                      : 'hover:bg-slate-50 text-slate-300'
                  }`}
                >
                  {item.dayNumber}
                </button>
              );
            })}
          </div>

          {/* Footer note: canonical date confirmation */}
          <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
            <span>Canonical Date:</span>
            <span className="font-mono font-bold text-blue-900 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
              {selectedDate}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default StaffDatePicker;
