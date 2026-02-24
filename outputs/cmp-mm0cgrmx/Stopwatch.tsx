import React from 'react';
import { useTimer } from '../hooks/useTimer';

const Stopwatch = () => {
  const [elapsedMs, isRunning, laps, start, pause, resume, reset, lap] = useTimer();
  
  // Render your stopwatch UI here using elapsedMs and isRunning
};

export default Stopwatch;