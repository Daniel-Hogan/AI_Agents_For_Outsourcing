import { useEffect, useState } from 'react';

import { apiJson } from '../../lib/api';

interface TimeSlot {
  day_of_week: number;
  start_time: string;
  end_time: string;
}

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// Helper function to generate times in 30-minute increments
const generateTimeOptions = () => {
  const times = [];
  for (let i = 0; i < 24; i++) {
    for (let j = 0; j < 60; j += 15) {
      const hour = i.toString().padStart(2, '0');
      const minute = j.toString().padStart(2, '0');
      times.push(`${hour}:${minute}`);
    }
  }
  return times;
};

// Helper to format "13:00" into "1:00 PM" for the display
const formatTimeDisplay = (time24: string) => {
  const [h, m] = time24.split(':');
  const date = new Date();
  date.setHours(parseInt(h, 10), parseInt(m, 10));
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

const TIME_OPTIONS = generateTimeOptions();

export default function AvailabilitySettings() {
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const fetchAvailability = async () => {
      try {
        const data = await apiJson<TimeSlot[]>('/api/availability/');
        setSlots(data);
      } catch (error) {
        console.error("Failed to fetch availability", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAvailability();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await apiJson<TimeSlot[]>('/api/availability/', {
        method: 'POST',
        body: JSON.stringify(slots)
      });
      alert("Working hours saved successfully!");
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : 'Failed to save schedule.');
    } finally {
      setIsSaving(false);
    }
  };

  const toggleDay = (dayIndex: number) => {
    if (slots.some(s => s.day_of_week === dayIndex)) {
      setSlots(slots.filter(s => s.day_of_week !== dayIndex));
    } else {
      setSlots([...slots, { day_of_week: dayIndex, start_time: '09:00:00', end_time: '17:00:00' }]);
    }
  };

  const updateTime = (dayIndex: number, field: 'start_time' | 'end_time', value: string) => {
    const formattedValue = value.length === 5 ? `${value}:00` : value;
    setSlots(slots.map(s => s.day_of_week === dayIndex ? { ...s, [field]: formattedValue } : s));
  };

  if (isLoading) return <div className="p-8 text-slate-400">Loading schedule...</div>;

  return (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm mt-6">
      <h2 className="text-xl font-bold text-slate-800 dark:text-white mb-6">Weekly Availability</h2>
      
      <div className="space-y-4">
        {DAYS.map((day, index) => {
          const slot = slots.find(s => s.day_of_week === index);
          const isActive = !!slot;

          return (
            <div key={day} className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
              <div className="flex items-center gap-4 w-1/3">
                <input 
                  type="checkbox" 
                  checked={isActive}
                  onChange={() => toggleDay(index)}
                  className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <span className={`font-medium ${isActive ? 'text-slate-900 dark:text-white' : 'text-slate-500'}`}>
                  {day}
                </span>
              </div>

              {isActive ? (
                <div className="flex items-center gap-3 flex-1 justify-end">
                  {/* Swapped input for a styled select dropdown */}
                  <select 
                    value={slot.start_time.slice(0, 5)} 
                    onChange={(e) => updateTime(index, 'start_time', e.target.value)}
                    className="px-3 py-2 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer custom-select"
                  >
                    {TIME_OPTIONS.map(time => (
                      <option key={`start-${time}`} value={time}>{formatTimeDisplay(time)}</option>
                    ))}
                  </select>

                  <span className="text-slate-400 text-sm font-medium">to</span>
                  
                  <select 
                    value={slot.end_time.slice(0, 5)}
                    onChange={(e) => updateTime(index, 'end_time', e.target.value)}
                    className="px-3 py-2 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer custom-select"
                  >
                    {TIME_OPTIONS.map(time => (
                      <option key={`end-${time}`} value={time}>{formatTimeDisplay(time)}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="flex-1 text-right text-slate-400 text-sm font-medium">
                  Unavailable
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-8 flex justify-end">
        <button 
          onClick={handleSave}
          disabled={isSaving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50"
        >
          {isSaving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
