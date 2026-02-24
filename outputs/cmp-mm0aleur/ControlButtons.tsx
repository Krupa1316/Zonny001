import React, { useContext } from 'react';
import Button from '@mui/material/Button';
import timerLogic from './timerLogic.ts';

const ControlButtons = () => {
  const { startTimer, pauseTimer, resetTimer, addLap } = useContext(timerLogic);
  
  return (
    <>
      <Button variant="contained" onClick={startTimer}>Start</Button>
      <Button variant="contained" color="primary" onClick={pauseTimer}>Pause</Button>
      <Button variant="contained" color="secondary" onClick={resetTimer}>Reset</Button>
      <Button variant="contained" color="success" onClick={addLap}>Add Lap</Button>
    </>
  );
};

export default ControlButtons;