import React from 'react'
import TimerProvider from './contexts/TimerContext'
import Stopwatch from './components/Stopwatch'
import ClockDisplay from './components/ClockDisplay'

const App = () => (
  <TimerProvider>
    <div className="app-container">
      <Stopwatch />
      <ClockDisplay />
    </div>
  </TimerProvider>
)

export default App