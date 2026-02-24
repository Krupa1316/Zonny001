import React from 'react';
import { useTimer } from '../hooks/useTimer';

const ClockDisplay = () => {
  const [, , , globalTime] = useTimer();
  
  // Render your clock display UI here using globalTime
};

export default ClockDisplay;