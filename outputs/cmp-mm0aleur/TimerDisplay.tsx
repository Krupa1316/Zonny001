import React, { useContext } from 'react';
import Typography from '@mui/material/Typography';
import timerLogic from './timerLogic.ts';

const TimerDisplay = () => {
  const { elapsedMs } = useContext(timerLogic);
  
  return (
    <Typography variant="h1">
      {formatElapsed(elapsedMs)}
    </Typography>
  );
};

export default TimerDisplay;