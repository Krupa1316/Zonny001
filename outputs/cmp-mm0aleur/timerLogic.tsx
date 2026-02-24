import React, { createContext, useState } from 'react';

const TimerContext = createContext();

let intervalId;

const TimerProvider = ({ children }) => {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  
  const startTimer = () => {
    if (!isRunning) {
      intervalId = setInterval(() => {
        setElapsedMs((prevMs) => prevMs + 100);
      }, 100);
      
      setIsRunning(true);
    }
  };
  
  const pauseTimer = () => {
    if (isRunning) {
      clearInterval(intervalId);
      setIsRunning(false);
    }
  };
  
  const resetTimer = () => {
    setElapsedMs(0);
  };
  
  return (
    <TimerContext.Provider value={{ elapsedMs, startTimer, pauseTimer, resetTimer }}>
      {children}
    </TimerContext.Provider>
  );
};

export default TimerProvider;