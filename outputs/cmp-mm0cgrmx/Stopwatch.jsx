import React, { useContext } from 'react'
import TimerContext from '../contexts/TimerContext'

const Stopwatch = () => {
  const { elapsedMs, isRunning, start, pause, resume, reset, lap } = useContext(TimerContext)
  
  // Render your stopwatch UI here using elapsedMs and isRunning
}

export default Stopwatch