import Constants, { AppOwnership } from 'expo-constants';
import { memo, useMemo } from 'react';
import { StyleSheet, Text } from 'react-native';
import { EnrichedMarkdownText } from 'react-native-enriched-markdown';

import { parseTutorContent } from '../markdown/parseTutorContent';

interface Props {
  text: string;
  streaming?: boolean;
}

function TutorMarkdownView({ text, streaming = false }: Props) {
  const parsed = useMemo(() => parseTutorContent(text), [text]);
  const requiresPlainText =
    streaming || parsed.hasIncompleteMath || Constants.appOwnership === AppOwnership.Expo;

  if (requiresPlainText) {
    return <Text style={styles.plainText}>{text || '…'}</Text>;
  }

  return (
    <EnrichedMarkdownText
      markdown={text || '…'}
      flavor="github"
      selectable
      enableTaskListItemToggle={false}
      markdownStyle={{
        paragraph: { color: '#172033', fontSize: 16, lineHeight: 23 },
        h1: { color: '#172033', fontSize: 22 },
        h2: { color: '#172033', fontSize: 20 },
        h3: { color: '#172033', fontSize: 18 },
        code: { color: '#24324A', backgroundColor: '#EEF1F6' },
        codeBlock: { color: '#24324A', backgroundColor: '#EEF1F6' },
      }}
      onLatexError={(event) => {
        if (__DEV__) console.warn('[tutor] latex_render_failed', event);
      }}
    />
  );
}

export const TutorMarkdown = memo(TutorMarkdownView);

const styles = StyleSheet.create({
  plainText: { color: '#172033', fontSize: 16, lineHeight: 23 },
});
