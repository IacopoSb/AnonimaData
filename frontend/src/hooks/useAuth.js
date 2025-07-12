import { useState, useEffect } from 'react';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from 'firebase/auth';
import '../services/firebase'; // Firebase is initialized here
import { getAuthErrorMessage } from '../utils/authErrors'; // Import utility for error messages

const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [firebaseLoaded, setFirebaseLoaded] = useState(false);

  useEffect(() => {
    const auth = getAuth();
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        setUser({
          uid: user.uid,
          name: user.displayName,
          email: user.email,
          avatar: user.photoURL
        });
      } else {
        setUser(null);
      }
      setLoading(false);
      setFirebaseLoaded(true);
    });
    return () => unsubscribe();
  }, []);

  const handleLogin = async () => {
    const auth = getAuth();
    const provider = new GoogleAuthProvider();
    try {
      setAuthError('');
      await signInWithPopup(auth, provider);
    } catch (error) {
      console.error('Authentication error:', error);
      setAuthError(getAuthErrorMessage(error.code));
    }
  };

  const handleLogout = async () => {
    const auth = getAuth();
    try {
      await signOut(auth);
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return { user, loading, authError, firebaseLoaded, handleLogin, handleLogout };
};

export default useAuth;