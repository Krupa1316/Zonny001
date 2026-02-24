import React, { createContext, useReducer, useEffect } from 'react'
import { getServerTime } from '../services/apiService'

const initialState = {
  elapsedMs: 0,
  isRunning: false,
  laps: [],
  globalTime: null,
}

function reducer(state, action) {
  switch (action.type) {
    // Handle state transitions here based on actions
    default:
      return state
  }
}

export const TimerContext = createContext()

const TimerProvider = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState)
  
  // Implement your timer logic and state management here using React's useEffect to get server time and start/pause/resume/reset/lap functionality
}

export default TimerProvider