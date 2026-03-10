import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

const Signup = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({ firstName: '', lastName: '', email: '', password: '' });
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/auth/register", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: formData.email, 
          password: formData.password, 
          first_name: formData.firstName, 
          last_name: formData.lastName 
        }),
      });

      if (response.ok) {
        alert("Account created! Please sign in.");
        navigate("/login");
      } else {
        const data = await response.json();
        alert(`Error: ${data.detail || "Registration failed"}`);
      }
    } catch (error) {
      alert("Backend connection failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
       <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-[120px]" />
       <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-[120px]" />

      <div className="relative w-full max-w-md p-8 bg-slate-900/40 border border-slate-800 backdrop-blur-2xl rounded-3xl shadow-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">Create Account</h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-4">
            <input 
              type="text" 
              required
              className="w-1/2 px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="First Name"
              onChange={(e) => setFormData({...formData, firstName: e.target.value})}
            />
            <input 
              type="text" 
              required
              className="w-1/2 px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Last Name"
              onChange={(e) => setFormData({...formData, lastName: e.target.value})}
            />
          </div>
          <input 
            type="email" 
            required
            className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Email Address"
            onChange={(e) => setFormData({...formData, email: e.target.value})}
          />
          <input 
            type="password" 
            required
            className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Password"
            onChange={(e) => setFormData({...formData, password: e.target.value})}
          />
          <button 
            type="submit" 
            disabled={isLoading}
            className="w-full py-3.5 px-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all"
          >
            {isLoading ? "Connecting..." : "Sign Up"}
          </button>
        </form>

        <div className="mt-8 text-center">
          <Link to="/login" className="text-sm text-slate-400 hover:text-blue-400 underline-offset-4 hover:underline">
            Already have an account? Log in
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Signup;