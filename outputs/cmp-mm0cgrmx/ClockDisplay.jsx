import React, { useContext } from 'react'
import TimerContext from '../contexts/TimerContext'

const ClockDisplay = () => {
  const { globalTime } = useContext(TimerContext)
  
  // Render your clock display UI here using globalTime
}

export default ClockDisplay