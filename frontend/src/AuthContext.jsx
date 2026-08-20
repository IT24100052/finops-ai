import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('finops_token'))
  const [user, setUser]   = useState(null)

  useEffect(() => {
    if (token) {
      // Decode the JWT payload (not verified — just for display)
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setUser({ email: payload.sub })
      } catch {
        setUser(null)
      }
    } else {
      setUser(null)
    }
  }, [token])

  const login = (newToken) => {
    localStorage.setItem('finops_token', newToken)
    setToken(newToken)
  }

  const logout = () => {
    localStorage.removeItem('finops_token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthed: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
