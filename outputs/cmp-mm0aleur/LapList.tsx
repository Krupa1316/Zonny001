import React from 'react';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import { useContext } from 'react';
import timerLogic from './timerLogic.ts';

const LapList = () => {
  const { laps } = useContext(timerLogic);
  
  return (
    <List>
      {laps.map((lap, index) => 
        <ListItem key={index}>Lap {index + 1}: {formatElapsed(lap)}</ListItem>
      )}
    </List>
  );
};

export default LapList;
```

Please note that this is a simplified version and does not cover all functionalities such as data persistence, theme switching, routing etc. The complete code would be much larger due to the complexity of the project. This code also assumes that you have already set up your development environment with Babel, Webpack, React, MUI, and TypeScript.