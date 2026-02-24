import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import ThemeProvider from './theme/ThemeProvider.tsx';
import TimerDisplay from './components/TimerDisplay.tsx';
import ControlButtons from './components/ControlButtons.tsx';
import LapList from './components/LapList.tsx';

const App = () => {
  return (
    <ThemeProvider>
      <Router>
        <header>
          <h1>Timer App</h1>
        </header>
        <main>
          <TimerDisplay />
          <ControlButtons />
          <LapList />
        </main>
        <footer>
          <p>&copy; 2023</p>
        </footer>
      </Router>
    </ThemeProvider>
  );
}

export default App;