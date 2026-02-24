import React, { createContext, useState } from 'react';
import { ThemeProvider as MuiThemeProvider, createTheme } from '@mui/material/styles';
import Button from '@mui/material/Button';

const darkTheme = createTheme({
  palette: { mode: 'dark' },
});

const lightTheme = createTheme({
  palette: { mode: 'light' },
});

export const ThemeContext = createContext();

const ThemeProvider = ({ children }) => {
  const [isDark, setIsDark] = useState(false);
  const theme = isDark ? darkTheme : lightTheme;

  return (
    <MuiThemeProvider theme={theme}>
      <Button onClick={() => setIsDark(!isDark)}>Toggle Theme</Button>
      {children}
    </MuiThemeProvider>
  );
};

export default ThemeProvider;