/**
 * RegisterPage — email/password registration has been removed.
 * This route now redirects users to the Microsoft OAuth login.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function RegisterPage() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate('/login', { replace: true });
  }, [navigate]);

  return null;
}