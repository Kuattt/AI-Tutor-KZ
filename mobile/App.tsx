import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { TutorChatScreen } from './src/screens/TutorChatScreen';

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <TutorChatScreen />
    </SafeAreaProvider>
  );
}
