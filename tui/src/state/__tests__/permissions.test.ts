import { describe, it, expect, beforeEach } from 'vitest';
import { PermissionStore } from '../permissions.js';

describe('PermissionStore', () => {
  let store: PermissionStore;

  beforeEach(() => {
    store = new PermissionStore();
  });

  it('starts empty', () => {
    expect(store.getGrants()).toHaveLength(0);
  });

  it('adds session grant correctly', () => {
    store.addSessionGrant('file_read');
    const grants = store.getGrants();
    expect(grants).toHaveLength(1);
    expect(grants[0]?.type).toBe('session');
    expect(grants[0]?.tool).toBe('file_read');
  });

  it('removes duplicate session grants for same tool', () => {
    store.addSessionGrant('file_read');
    store.addSessionGrant('file_read');
    expect(store.getGrants()).toHaveLength(1);
  });

  it('allows multiple session grants for different tools', () => {
    store.addSessionGrant('file_read');
    store.addSessionGrant('file_write');
    expect(store.getGrants()).toHaveLength(2);
  });

  it('auto-approves session granted tool', () => {
    store.addSessionGrant('file_read');
    expect(store.isAutoApproved('file_read', {})).toBe(true);
  });

  it('does not auto-approve ungranted tool', () => {
    store.addSessionGrant('file_read');
    expect(store.isAutoApproved('file_write', {})).toBe(false);
  });

  it('adds similar grant correctly', () => {
    store.addSimilarGrant('git_commit', { message: 'fix' });
    const grants = store.getGrants();
    expect(grants).toHaveLength(1);
    expect(grants[0]?.type).toBe('similar');
    expect(grants[0]?.argPattern).toEqual({ message: 'fix' });
  });

  it('auto-approves similar granted tool with matching args', () => {
    store.addSimilarGrant('git_commit', { branch: 'main' });
    expect(store.isAutoApproved('git_commit', { branch: 'main', message: 'test' })).toBe(true);
  });

  it('does not auto-approve similar granted tool with non-matching args', () => {
    store.addSimilarGrant('git_commit', { branch: 'main' });
    expect(store.isAutoApproved('git_commit', { branch: 'dev' })).toBe(false);
  });

  it('revokes grant by id', () => {
    store.addSessionGrant('file_read');
    const id = store.getGrants()[0]!.id;
    store.revokeGrant(id);
    expect(store.getGrants()).toHaveLength(0);
  });

  it('clears all grants', () => {
    store.addSessionGrant('file_read');
    store.addSimilarGrant('file_write', {});
    store.clear();
    expect(store.getGrants()).toHaveLength(0);
  });
});
