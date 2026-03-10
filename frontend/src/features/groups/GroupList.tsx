import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface Group {
  id: number;
  name: string;
  description: string;
  role: string;
}

export default function GroupList() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchGroups = async () => {
      // 1. Get the token saved during login
      const token = localStorage.getItem('access_token');
      
      if (!token) {
        // If no token, kick them back to login
        navigate('/login');
        return;
      }

      try {
        // 2. Fetch the groups from FastAPI
        const response = await fetch('http://127.0.0.1:8000/groups/', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const data = await response.json();
          setGroups(data);
        } else if (response.status === 401) {
          // Token expired or invalid
          localStorage.removeItem('access_token');
          navigate('/login');
        } else {
          setError('Failed to fetch groups.');
        }
      } catch (err) {
        setError('Could not connect to the backend server.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchGroups();
  }, [navigate]);

  if (isLoading) return <div className="p-8 text-slate-400">Loading your teams...</div>;
  if (error) return <div className="p-8 text-red-400">{error}</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-slate-800 dark:text-white">Your Groups</h1>
        <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition">
          + Create Group
        </button>
      </div>
      
      {groups.length === 0 ? (
        <div className="bg-slate-100 dark:bg-slate-800 rounded-xl p-8 text-center border border-slate-200 dark:border-slate-700">
          <p className="text-slate-500 dark:text-slate-400">You are not a member of any groups yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {groups.map((group) => (
            <div key={group.id} className="bg-white dark:bg-slate-800 p-6 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-md transition">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-xl font-semibold text-slate-800 dark:text-white">{group.name}</h3>
                <span className="px-2.5 py-1 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 rounded-full capitalize">
                  {group.role}
                </span>
              </div>
              <p className="text-slate-500 dark:text-slate-400 text-sm">
                {group.description || 'No description provided.'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
